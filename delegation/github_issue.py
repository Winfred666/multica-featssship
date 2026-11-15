"""Optional existing GitHub source issue and its verified resolution."""
import re


def issue_link(url):
    if url and not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+/issues/[1-9][0-9]*', url):
        raise ValueError('Supply an existing GitHub issue URL: https://github.com/OWNER/REPO/issues/NUMBER')
    return url
