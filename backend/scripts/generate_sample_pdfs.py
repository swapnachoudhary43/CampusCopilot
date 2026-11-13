"""Do not generate university PDFs.

Earlier versions of this script wrote fictional Northbridge Institute documents.
Those files have been removed. Official PDFs belong in
data/official_documents/davv/ and are listed in manifest.json.
"""

import sys


def generate_all():
    raise RuntimeError(
        "Fictional university PDFs are not generated. "
        "Use the public files in data/official_documents/davv/."
    )


if __name__ == "__main__":
    print(generate_all.__doc__ if False else "Refusing to invent institutional PDFs.")
    print("See data/official_documents/davv/manifest.json and docs/DATA_SOURCES_AND_PROVENANCE.md.")
    sys.exit(1)
