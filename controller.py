"""The only root SOP: dispatch one feature and let MAIN receive its result."""
import json
from pathlib import Path

from common import QUESTIONS, block, cli, comment, entry_command, unpack, write_json
from github_issue import issue_link, mirror_title
from packages import compile_review
from sop import Option, Parameter, State, Workflow

ROOT = Path(__file__).resolve().parent
SPEC_PARAMS = (
    Parameter('--title', 'Feature/fix title'), Parameter('--request', 'Requested behavior'),
    Parameter('--direction', 'Configured direction name'), Parameter('--scope', 'Feature/fix scope'),
    Parameter('--question', 'Acceptance question'),
    Parameter('--test-command', 'Verification command; defaults to the configured direction', required=False),
    Parameter('--github-issue', 'Optional existing GitHub source issue URL', required=False),
)
EDIT_PARAMS = tuple(Parameter(param.flag, param.prompt, required=False) for param in SPEC_PARAMS)


def configured(context):
    config = json.loads((ROOT / 'installation.json').read_text())
    if (context['workspace_id'], context['issue_id'], context['agent_id']) != (config['workspace_id'], config['root_issue_id'], config['main_id']):
        raise ValueError('Delegation belongs to the configured MAIN root and native identity.')
    context['config'] = config
    if context['args'].thread:
        context['state']['reply_parent'] = context['args'].thread
    if context['args'].spec:
        context['state'].setdefault('spec_id', context['args'].spec)
    return config


def direction(config, name):
    selected = next((d for d in config['directions'] if d['name'] == name), None)
    if not selected:
        raise ValueError('Choose a configured direction: ' + ', '.join(d['name'] for d in config['directions']))
    return selected


def publish_spec(context, spec):
    row = comment(context['issue_id'], block('spec', spec),
                  context['args'].thread or context['state'].get('reply_parent') or context['state'].get('spec_id'))
    context['state']['spec_id'] = row['id']
    return {'data': {'spec_id': row['id'], 'spec': spec}}


def read_spec(context):
    target = context['state'].get('spec_id') or context['args'].spec or context['args'].thread or context['state'].get('reply_parent')
    if not target:
        raise ValueError('Draft a specification first, or reopen it with --spec <draft comment UUID>.')
    rows = cli('issue', 'comment', 'list', context['issue_id'], '--thread', target, '--tail', '30')
    drafts = [(unpack(row.get('content', ''), 'spec'), row) for row in rows
              if row.get('author_type') == 'agent' and row.get('author_id') == context['config']['main_id']
              and unpack(row.get('content', ''), 'spec')]
    if not drafts:
        raise ValueError('This thread has no MAIN specification draft.')
    spec, row = drafts[-1]
    context['state']['spec_id'] = row['id']
    return spec, row, rows


def propose(args, context):
    if context['state'].get('spec_id'):
        spec, row, _ = read_spec(context)
        return {'data': {'spec_id': row['id'], 'spec': spec}}
    selected = direction(context['config'], args.direction)
    spec = {key: getattr(args, key) for key in ('title', 'request', 'direction', 'scope', 'question')}
    spec['test_command'] = args.test_command or selected['test_command']
    spec['questions'] = list(QUESTIONS)
    url = issue_link(args.title, args.github_issue)
    if url:
        spec['github_issue'] = url
    return publish_spec(context, spec)


def drafting_options(context):
    return (Option('propose', 'grilling', 'Draft the delegation config, or reopen --spec unchanged.', propose,
                   params=() if context['state'].get('spec_id') else SPEC_PARAMS),)


def edit(args, context):
    patch = {param.flag[2:].replace('-', '_'): getattr(args, param.flag[2:].replace('-', '_'))
             for param in EDIT_PARAMS if getattr(args, param.flag[2:].replace('-', '_')) is not None}
    if len(patch) != 1:
        raise ValueError('Ask the human one question, then supply exactly one field to edit.')
    if not next(iter(patch.values())).strip():
        raise ValueError('The edited field must not be blank.')
    spec, _, _ = read_spec(context)
    spec.update(patch)
    direction(context['config'], spec['direction'])
    url = issue_link(spec['title'], spec.get('github_issue'))
    if url:
        spec['github_issue'] = url
    return publish_spec(context, spec)


def dispatch(args, context):
    config = context['config']
    request, spec_row, rows = read_spec(context)
    direction(config, request['direction'])
    # Persist the created ID before compiling or waking an agent; a retry reuses it.
    receipt = ROOT / '.state' / (spec_row['id'] + '-dispatch.json')
    owned = json.loads(receipt.read_text()) if receipt.exists() else {}
    if owned.get('request', request) != request:
        raise ValueError('The dispatch checkpoint belongs to a different draft.')
    previous = next((row for row in rows if row.get('author_type') == 'agent' and row.get('author_id') == config['main_id']
                     and (unpack(row.get('content', ''), 'dispatch') or {}).get('spec_id') == spec_row['id']), None)
    if previous:
        owned.update(unpack(previous['content'], 'dispatch'), main_thread_id=previous['id'])
        child = cli('issue', 'get', owned['issue_id'])
        if unpack(child['description'], 'binding') and child['status'] != 'backlog':
            return {'data': {'issue_id': child['id']}, 'instruction': 'Already dispatched; end this turn.'}
    binding = {key: config[key] for key in ('workspace_id', 'project_id', 'root_issue_id', 'main_id', 'developer_id', 'reviewer_id', 'repository')}
    binding.update(request, spec_id=spec_row['id'])
    url = request.get('github_issue')
    if url:
        binding['title'] = mirror_title(request['title'], url)
    if 'issue_id' not in owned:
        child = cli('issue', 'create', '--title', binding['title'], '--description-stdin', '--parent', context['issue_id'],
                    '--project', config['project_id'], '--assignee-id', config['developer_id'], '--status', 'backlog', input=binding['request'])
        owned = {'issue_id': child['id'], 'request': request}
        write_json(receipt, owned)
    binding.update(issue_id=owned['issue_id'], branch='featssship/' + owned['issue_id'])
    if 'thread_id' not in owned:
        row = comment(binding['issue_id'], 'Feature implementation, review and integration.')
        owned['thread_id'] = row['id']
        write_json(receipt, owned)
    binding['thread_id'] = owned['thread_id']
    if 'main_thread_id' not in owned:
        row = comment(context['issue_id'], block('dispatch', {'spec_id': spec_row['id'],
                      'issue_id': binding['issue_id'], 'thread_id': binding['thread_id']}),
                      args.thread or context['state'].get('reply_parent') or spec_row['id'])
        owned['main_thread_id'] = row['id']
        write_json(receipt, owned)
    binding['main_thread_id'] = owned['main_thread_id']
    binding['reviewer_skill_id'] = owned.get('reviewer_skill_id')
    name, skill_id = compile_review(binding)
    owned['reviewer_skill_id'] = skill_id
    write_json(receipt, owned)
    binding['reviewer_skill_id'] = skill_id
    description = (binding['request'] + '\n\nScope: ' + binding['scope'] + '\n\nAcceptance: ' + binding['question'] +
                   '\n\n' + '\n'.join('- ' + q for q in binding['questions']) + '\n\n' + entry_command('multica-featssship-developer') +
                   '\n\n' + block('binding', binding))
    cli('issue', 'update', binding['issue_id'], '--description-stdin', '--no-start', input=description)
    child = cli('issue', 'get', binding['issue_id'])
    if child['status'] == 'backlog':
        cli('issue', 'status', binding['issue_id'], 'todo')
    owned['completed'] = True
    write_json(receipt, owned)
    return {'data': {'issue_id': binding['issue_id'], 'reviewer_skill': name},
            'instruction': 'Dispatched; end this turn.'}


workflow = Workflow(
    State('drafting', 'Draft the delegation config from the request and available facts: behavior, scope, '
          'acceptance and verification. Reuse answered decisions. Choose propose to inspect the draft.',
          initial=True, precheck=configured, options=drafting_options),
    # TODO: This is Agent-as-Middleware. More efficient SoP interact with human should
    # hard stop agent, hijack the UI to the surface, and let human or any ouer entity
    # directly filling the param needed for next. This should be a part of remote
    # SoP calling in the future.
    State('grilling', 'Inspect the draft for clarity. If a point is unclear, ask the human one question '
          'with a recommended answer and end this turn. After their reply, use edit to patch only that point; '
          'repeat one question at a time. All edit fields are optional; supply exactly one. '
          'Otherwise choose dispatch directly.', precheck=configured, options=(
        Option('edit', 'grilling', 'After the human answers one question, patch one point using one optional flag: '
               + ', '.join(param.flag for param in EDIT_PARAMS), edit,
               params=EDIT_PARAMS),
        Option('dispatch', 'finished', 'Delegate the draft and prepare the feature resources.', dispatch),
    )),
    State('finished', 'MAIN waits for one verified result from the feature issue.', final=True),
    params=(Parameter('--thread', 'Native MAIN trigger comment UUID', required=False),
            Parameter('--spec', 'Existing draft comment UUID to reopen in a new task', required=False)),
)
