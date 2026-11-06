# Architecture

In 2024 we started moving off the monolith. At first everything lived in one Rails app that handled the website, the
API and the nightly billing jobs. As traffic grew, the billing jobs began to slow the website down, so we decided to
split them out.

The first step was to move billing into its own service. We tried a shared database at first, but it caused locking
problems, so in the second phase we gave billing its own Postgres database and put a queue (SQS) between the two.

Next we moved the API. The Rails app now serves only the website, and the API is a Go service behind the same load
balancer. Finally, in 2025, we retired the old cron box, and the billing jobs now run as scheduled tasks in ECS.
