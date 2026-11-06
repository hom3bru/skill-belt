from app.export import export_csv


def run(rows):
    export_csv(rows, "/var/exports/nightly.csv")
