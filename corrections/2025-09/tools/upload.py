"""Compatibility entry point for the validated full-month publisher.

Run without dates for a dry run; --go publishes the complete checked month.
See publish.py for resume and retry controls.
"""
from publish import main

if __name__ == '__main__':
    main()
