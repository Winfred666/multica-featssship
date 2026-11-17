"""Choose complete bundles at installation/update, never inside a procedure."""


def roles(config):
    enabled = config.get('develop_reviewer_split', False)
    if not isinstance(enabled, bool):
        raise ValueError('develop_reviewer_split must be true or false.')
    return ('split-delegation', 'split-feature') if enabled else ('delegation', 'feature')
