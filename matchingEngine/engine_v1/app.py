import redis
from sanic import Sanic
from sanic.response import json, text



# connect to redis
try:
    conn = redis.StrictRedis(
        host='localhost',
        port=6379)
    print(conn)
    conn.ping()
    print('Connected!')
except Exception as ex:
    print('Error:', ex)
    exit('Failed to connect, terminating.')



# setup server
app = Sanic()

async def test_if_alive(request):
    response = json({
            'message':'I am alive.',
            'received': request.json
        })
    return response

app.add_route(controller.test, '/test-if-alive', methods=['POST'])

def run():
    app.run(host="0.0.0.0", port=5000)