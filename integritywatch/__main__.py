"""Allow running the tool with: python3 -m integritywatch"""

import sys

from .cli import main

sys.exit(main())
