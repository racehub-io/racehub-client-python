import asyncio
import grpc
import racehub_client_python.utils.racehub_pb2 as racehub_pb2
import racehub_client_python.utils.racehub_pb2_grpc as racehub_pb2_grpc


async def chat_bidi(stub):
    async def request_gen():
        # Send a FooMessage first
        yield racehub_pb2.StreamMessage(
            context="client-1",
            foo=racehub_pb2.FooMessage(foo_text="Hello from Foo", foo_count=10),
        )
        await asyncio.sleep(1)

        # Next, a BarMessage
        yield racehub_pb2.StreamMessage(
            context="client-1",
            bar=racehub_pb2.BarMessage(bar_flag=True),
        )
        await asyncio.sleep(1)

        # Finally, a BazMessage
        yield racehub_pb2.StreamMessage(
            context="client-1",
            baz=racehub_pb2.BazMessage(baz_value=3.14, baz_comment="Pi is here"),
        )
        # Then end stream from client side

    # We read server's responses in a loop
    async for response in stub.Chat(request_gen()):
        if response.HasField("foo"):
            foo = response.foo
            print(
                f"Got FooMessage from server: foo_text={foo.foo_text}, foo_count={foo.foo_count}"
            )
        elif response.HasField("bar"):
            bar = response.bar
            print(f"Got BarMessage from server: bar_flag={bar.bar_flag}")
        elif response.HasField("baz"):
            baz = response.baz
            print(
                f"Got BazMessage from server: baz_value={baz.baz_value}, comment={baz.baz_comment}"
            )
        else:
            print("Got unknown or empty payload from server.")


async def main():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = racehub_pb2_grpc.BroadcasterStub(channel)
        await chat_bidi(stub)


if __name__ == "__main__":
    asyncio.run(main())
