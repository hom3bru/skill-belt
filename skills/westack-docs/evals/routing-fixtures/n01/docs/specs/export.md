# Spec: scheduled exports

## Goal

Let an admin schedule a daily or weekly export of all invoices to their own S3 bucket.

## Design

- The admin enters a bucket name and an access key pair in settings.
- A nightly job lists the schedules due that day and writes one CSV per schedule to the bucket.
- A failed export is retried the next night.

## Out of scope

- Formats other than CSV.
- Destinations other than S3.
