<!-- bug-p2b -->
# Memory grows during the nightly export

The export reads a 4 GB CSV with `tabular_io.reader.stream()` (tabular-io 5.2.1). Resident memory climbs steadily
until the job is killed at 8 GB. Reading the same file with `read_chunks()` stays flat at about 300 MB.
