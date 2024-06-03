import datetime


now1 = datetime.datetime.now()
u_now1 = now1.timestamp()

now2 = datetime.datetime.fromtimestamp(u_now1)
u_now2 = now2.timestamp()

print(u_now1)
print(u_now2)

assert u_now1 == u_now2
