import redis
from time import sleep, gmtime, strftime, time
import ujson
import requests as requestsClient
from greedyMatcher import GreedyMatcher
from DynamicTripVehicleAssignmentMatcher import DynamicTripVehicleAssignmentMatcher
import sys

# redis key name, refer to README for the data struture
RIDE_REQUEST = 'realTimeRideRequest'
DRIVER_LOCATION = 'driverLocation'
DRIVER_ON_GOING_RIDE = 'driverOngoingRide'
SERVER_ENDPOINT = 'http://localhost/notify-match-result/real-time-ride'
ALGO_VERSION = 'v2'

def getTimeStr():
    return strftime("%Y-%m-%d %H:%M:%S", gmtime())

def startEngine():
    # connect to redis
    try:
        redisConn = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)
        print('Connected to redis')
    except Exception as ex:
        print('Error:', ex)
        exit('Failed to connect, terminating.')

    if sys.argv[0]=='greedy':
        print('using GreedyMatcher')
        matcher = GreedyMatcher({ 'maxMatchDistance': 1500 })
    else:
        print('using DynamicTripVehicleAssignmentMatcher')
        matcher = DynamicTripVehicleAssignmentMatcher({ 'maxMatchDistance': 1500 })

    while True:

        sleep(5)

        queueLen = redisConn.llen(RIDE_REQUEST)
        onlineDriverCount = redisConn.hlen(DRIVER_LOCATION)

        if queueLen==0 or onlineDriverCount==0:
            continue

        requests = []
        drivers = []
        
        # get all requests
        rideRequest = redisConn.lrange(RIDE_REQUEST, 0, -1)
        numOfReq = len(rideRequest)
        # remove the received request
        redisConn.ltrim(RIDE_REQUEST, numOfReq, -1)
        requests = [ ujson.loads(r) for r in rideRequest ]
        
        # get all driver locations
        driverLocationDict = redisConn.hgetall(DRIVER_LOCATION)
        for (driverId, locationJson) in driverLocationDict.items():
            location = ujson.loads( locationJson )

            if( isDriverOnline(location) ):
                ongoingRideListJson = redisConn.hget(DRIVER_ON_GOING_RIDE, driverId)
                if(ongoingRideListJson!=None):
                    ongoingRideList = ujson.loads(ongoingRideListJson)
                else:
                    ongoingRideList = []
                # print(len(ongoingRideList))

                drivers.append({
                    "userId": driverId,
                    "location": location['location'],
                    "capacity": 4,
                    "ongoingRide": ongoingRideList
                })
            # end of if
        # end of for
        
        if len(requests)>0 and len(drivers)>0:
            try:
                # match
                mappings, remainingRequests = matcher.match(requests, drivers)

                print("[{}] : ".format( getTimeStr() ), 'mapping (passenger->driver): ')
                for q, d in mappings:
                    print("  %s -> %s" %(q['userId'], d['userId']))
                print('remaining requests: ', len(remainingRequests))

                for mapping in mappings:
                    r, d = mapping
                    matchResult = {
                        "rider": r,
                        "driver": {
                            "userId": d['userId'],
                            "location": d['location']
                        },
                        "timestamp": time(),
                        "algoVersion": ALGO_VERSION
                    }
                    requestsClient.post(url = SERVER_ENDPOINT, json = matchResult)
                # end of for
            except Exception as e:
                # push back the unhandled requests
                requestsJsons = [ ujson.dumps(r) for r in requests ]
                redisConn.rpush(RIDE_REQUEST, *requestsJsons)
                raise e
            
            # push back the unhandled requests
            if len(remainingRequests)>0:
                remainingRequestJsons = [ ujson.dumps(r) for r in remainingRequests ]
                redisConn.rpush(RIDE_REQUEST, *remainingRequestJsons)
            # end of if
            
        # end of if
    # end of while


def isDriverOnline(driverLocation):
    # print("[{}] : ".format( getTimeStr() ), ' location time: ', driverLocation['timestamp'])
    currentTime = time()*1000
    return bool(currentTime - float(driverLocation['timestamp']) <= 7000.0)


if __name__ == '__main__':
    startEngine()