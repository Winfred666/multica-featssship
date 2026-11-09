"""Optional existing GitHub source issue and its verified resolution."""
import re


def issue_link(title, explicit=None):
    mirror = re.fullmatch(r'\[(.+)\]\((https://github\.com/[^\s)]+)\)', title)
    url = explicit or (mirror[2] if mirror else None)
    if url and not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+/issues/[1-9][0-9]*', url):
        raise ValueError('Supply an existing GitHub issue URL: https://github.com/OWNER/REPO/issues/NUMBER')
    if explicit and mirror and mirror[2] != explicit:
        raise ValueError('The title and --github-issue must identify the same source issue.')
    return url


def mirror_title(title, url):
    return title if issue_link(title) else f'[{title}]({url})'
