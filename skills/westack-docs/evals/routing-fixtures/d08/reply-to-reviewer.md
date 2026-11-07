Thanks for the careful review, and sorry for the slow reply. It has been a busy couple of weeks on our side and I
wanted to make sure I answered everything properly rather than rushing it.

On your first point, about whether the cache actually helps: I think it does, and to check this I ran the benchmark
again on the same machine as before (8 cores, 32 GB) with the cache on and off. With the cache off, the median request
took 182 ms and the 95th percentile was 410 ms. With the cache on, the median was 61 ms and the 95th percentile was
133 ms. So I think that is a fairly clear improvement, although of course it depends on the workload.

On your second point, about memory: memory use went from 1.1 GB to 1.4 GB with the cache on, which I think is
acceptable, but I am happy to add a size limit if you think that would be better.

Let me know if anything else needs changing and I will get to it as soon as I can.
