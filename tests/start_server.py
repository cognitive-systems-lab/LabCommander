import labc
labc.subscribe(print)
labc.subscribe(print, topic="", raw=True)
labc.register(lambda : "pong", name="ping")
labc.serve()
