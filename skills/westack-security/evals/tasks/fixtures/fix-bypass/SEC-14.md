# SEC-14: path traversal in file downloads (fxb-ticket-2d7)

Reported: a download of `../secret.txt` returned the contents of `secret.txt`, a file outside `uploads/`.

Fix (merged in PR-212): `app/files.py` now strips `../` from the requested name before joining it to the uploads folder. `tests/test_files.py` covers the reported request.
