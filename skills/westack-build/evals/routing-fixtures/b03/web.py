from checkout import checkout


def pay(request):
    receipt = checkout(request["cart"], request["token"])
    return {"status": 200, "body": receipt}
