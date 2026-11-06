from export import export_csv


def export_button(request):
    return {"status": 200, "headers": {"Content-Type": "text/csv"}, "body": export_csv(request["user_id"])}
