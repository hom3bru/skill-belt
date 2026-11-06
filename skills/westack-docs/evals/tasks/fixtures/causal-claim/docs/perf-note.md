<!-- perf-note-4b1 -->
## Allocator switch, week 41

In our two benchmark runs, both on Linux, peak memory with the new allocator was 1.8 GB against 2.4 GB before the switch. The drop coincided with the switch; the cache change that landed the same week has not been ruled out. We have not measured macOS or Windows.
