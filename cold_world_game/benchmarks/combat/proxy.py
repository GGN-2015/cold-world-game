import asyncio


class LatencyProxy:
    def __init__(self, upstream_port, latency_ms):
        self.upstream_port = upstream_port
        self.delay = latency_ms / 2000
        self.server = None
        self.tasks = set()

    async def start(self):
        self.server = await asyncio.start_server(self.accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def accept(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        upstream_writer = None
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection("127.0.0.1", self.upstream_port)
            await asyncio.gather(self.forward(reader, upstream_writer), self.forward(upstream_reader, writer))
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            if upstream_writer:
                upstream_writer.close()
            self.tasks.discard(task)

    async def forward(self, reader, writer):
        queue = asyncio.Queue(maxsize=64)

        async def receive():
            while True:
                data = await reader.read(65536)
                await queue.put((asyncio.get_running_loop().time() + self.delay, data))
                if not data:
                    return

        async def deliver():
            while True:
                deadline, data = await queue.get()
                await asyncio.sleep(max(0, deadline - asyncio.get_running_loop().time()))
                if not data:
                    if writer.can_write_eof():
                        writer.write_eof()
                    return
                writer.write(data)
                await writer.drain()

        receivers = [asyncio.create_task(receive()), asyncio.create_task(deliver())]
        try:
            await asyncio.gather(*receivers)
        finally:
            for task in receivers:
                task.cancel()
            await asyncio.gather(*receivers, return_exceptions=True)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
