"""Build-time version marker.

Overwritten by .github/workflows/release-windows.yml with the pushed git tag
(e.g. "v1.4.0") before packaging the Windows executable. Untouched local/dev
checkouts report "dev".
"""

__version__ = "dev"
