from .export import export_csv


def export_view(request, rows):
    export_csv(rows, "/tmp/export.csv")
    return {"status": 200, "file": "/tmp/export.csv"}
