# Instructions

Hello!

To run this "service stack", it's enough to run 
```docker-compose up``` 
from project root directory.
API part is easily scaleable by adding `--scale api=n`, for example:

```docker-compose up scale api=4```

As of now IP addresses of APIs may be found out by reading docker compose output:
 
 ```
api_1        | Listening on: 172.19.0.3:58169
api_2        | Listening on: 172.19.0.4:36705
```

 or by running `docker inspect nanobit_api_<number>| grep IPAddress`.
 We could use Nginx, but I understood primary goal was to establish permanent connections, so adding
 Nginx or some other load balancer should be on TODO list for this project.
 
To connect to our system, I used netcat. There are two possible commands: `get` and `set`, with
`set` always being followed by user and his favourite number: `set user number`. Connection and usage example:

```
▶ nc -c 172.19.0.4 36705
get
[(b'a', b'5'), (b'skux', b'50')]
b"[(b'a', b'5'), (b'skux', b'30')]"
get
[(b'a', b'5'), (b'skux', b'30')]
set mile 600
b"[(b'a', b'5'), (b'mile', b'600'), (b'skux', b'30')]"
```

With first line after first get coming from other client which set "skux" favourite number to 30.

