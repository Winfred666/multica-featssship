"""The only root SOP: dispatch one feature and let MAIN receive its result."""
import json
from pathlib import Path

from common import QUESTIONS, block, cli, comment, entry_command, write_json
from packages import compile_review
from sop import Option, Parameter, State, Workflow

ROOT = Path(__file__).resolve().parent


def configured(context):
    config = json.loads((ROOT / 'installation.json').read_text())
    if (context['workspace_id'], context['issue_id'], context['agent_id']) != (config['workspace_id'], config['root_issue_id'], config['main_id']):
        raise ValueError('Delegation belongs to the configured MAIN root and native identity.')
    context['config'] = config
    return config


def dispatch(args, context):
    config = context['config']
    direction = next((d for d in config['directions'] if d['name'] == args.direction), None)
    if not direction:
        raise ValueError('Choose a configured direction: ' + ', '.join(d['name'] for d in config['directions']))
    # Persist the created ID before compiling or waking an agent; a retry reuses it.
    receipt = ROOT / '.state' / (context['task_id'] + '-dispatch.json')
    owned = json.loads(receipt.read_text()) if receipt.exists() else {}
    request = {'title': args.title, 'request': args.request, 'direction': args.direction, 'question': args.question or direction['question']}
    if owned and owned['request'] != request:
        if not owned.get('completed'):
            raise ValueError('Resume this task’s recorded dispatch before starting another request.')
        owned = {}
    binding = {key: config[key] for key in ('workspace_id', 'project_id', 'root_issue_id', 'main_id', 'developer_id', 'reviewer_id', 'repository')}
    binding.update(request, scope=direction['scope'], test_command=direction['test_command'], questions=list(QUESTIONS))
    if 'issue_id' not in owned:
        child = cli('issue', 'create', '--title', args.title, '--description-stdin', '--parent', context['issue_id'],
                    '--project', config['project_id'], '--assignee-id', config['developer_id'], '--status', 'backlog', input=args.request)
        owned = {'issue_id': child['id'], 'request': request}
        write_json(receipt, owned)
    binding.update(issue_id=owned['issue_id'], branch='featssship/' + owned['issue_id'])
    if 'thread_id' not in owned:
        row = comment(binding['issue_id'], 'Feature implementation, review and integration share this thread.')
        owned['thread_id'] = row['id']
        write_json(receipt, owned)
    binding['thread_id'] = owned['thread_id']
    if 'main_thread_id' not in owned:
        row = comment(context['issue_id'], 'Dispatched feature ' + binding['issue_id'] + '. Its verified result will arrive here.', args.thread)
        owned['main_thread_id'] = row['id']
        write_json(receipt, owned)
    binding['main_thread_id'] = owned['main_thread_id']
    binding['reviewer_skill_id'] = owned.get('reviewer_skill_id')
    name, skill_id = compile_review(binding)
    owned['reviewer_skill_id'] = skill_id
    write_json(receipt, owned)
    binding['reviewer_skill_id'] = skill_id
    description = (args.request + '\n\nScope: ' + direction['scope'] + '\n\nAcceptance: ' + binding['question'] +
                   '\n\n' + '\n'.join('- ' + q for q in QUESTIONS) + '\n\n' + entry_command('multica-featssship-developer') +
                   '\n\n' + block('binding', binding))
    cli('issue', 'update', binding['issue_id'], '--description-stdin', '--no-start', input=description)
    child = cli('issue', 'get', binding['issue_id'])
    if child['status'] == 'backlog':
        cli('issue', 'status', binding['issue_id'], 'todo')
    owned['completed'] = True
    write_json(receipt, owned)
    return {'data': {'issue_id': binding['issue_id'], 'reviewer_skill': name},
            'instruction': 'Feature dispatched. MAIN receives its result in this thread; end this turn.'}


workflow = Workflow(
    State('delegate', 'Dispatch one configured feature/fix request.', initial=True, precheck=configured, options=(
        Option('dispatch', 'finished', 'Create or resume this feature dispatch.', dispatch, params=(
            Parameter('--title', 'Feature/fix title'), Parameter('--request', 'Original requested behavior'),
            Parameter('--direction', 'Configured direction name'), Parameter('--question', 'Acceptance question override', required=False),
            Parameter('--thread', 'Native MAIN trigger comment, when this run is a reply', required=False),)),)),
    State('finished', 'MAIN waits for one verified result from the feature issue.', final=True),
)
