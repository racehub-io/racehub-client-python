import asyncio
import logging
import grpc

# Generated modules from your proto
import racehub_client_python.utils.racehub_pb2 as racehub_pb2
import racehub_client_python.utils.racehub_pb2_grpc as racehub_pb2_grpc

logger = logging.getLogger(__name__)


class BroadcasterServicer(racehub_pb2_grpc.BroadcasterServicer):
    def __init__(self):
        # Keep track of connected client queues for broadcasting
        self._connected_clients = []

    async def Chat(self, request_iterator, context):
        """
        Bidirectional streaming method. We'll read from `request_iterator`
        (client → server) and also write messages to the client (server → client).
        """
        send_queue = asyncio.Queue()
        self._connected_clients.append(send_queue)

        logger.info("Client connected to Chat()")

        # Task to read from client
        recv_task = asyncio.create_task(self._recv_loop(request_iterator, send_queue))

        try:
            # Continuously yield back to the client from send_queue
            while True:
                message = await send_queue.get()  # a StreamMessage
                yield message
        except asyncio.CancelledError:
            logger.info("Chat stream cancelled (server side).")
        finally:
            logger.info("Client disconnected from Chat()")
            self._connected_clients.remove(send_queue)
            recv_task.cancel()

    async def _recv_loop(self, request_iterator, send_queue):
        """
        Handles inbound messages from this client. The client might be sending
        any of our typed sub-messages (FooMessage, BarMessage, BazMessage).
        """
        try:
            async for incoming in request_iterator:
                # Which oneof field is set?
                if incoming.HasField("foo"):
                    foo_msg = incoming.foo
                    logger.info(
                        f"Got FooMessage: foo_text={foo_msg.foo_text}, "
                        f"foo_count={foo_msg.foo_count}"
                    )
                    # Example response: we can respond with a BazMessage
                    response = racehub_pb2.StreamMessage(
                        context="server-response",
                        baz=racehub_pb2.BazMessage(
                            baz_value=42.0, baz_comment="Here is your response!"
                        ),
                    )
                    send_queue.put_nowait(response)

                elif incoming.HasField("bar"):
                    bar_msg = incoming.bar
                    logger.info(f"Got BarMessage: bar_flag={bar_msg.bar_flag}")
                    # Respond with a FooMessage
                    response = racehub_pb2.StreamMessage(
                        context="server-response",
                        foo=racehub_pb2.FooMessage(
                            foo_text="Received your BarMessage!", foo_count=123
                        ),
                    )
                    send_queue.put_nowait(response)

                elif incoming.HasField("baz"):
                    baz_msg = incoming.baz
                    logger.info(
                        f"Got BazMessage: baz_value={baz_msg.baz_value}, "
                        f"baz_comment={baz_msg.baz_comment}"
                    )
                    # Possibly no immediate response, or a different typed message
                    response = racehub_pb2.StreamMessage(
                        context="server-response",
                        bar=racehub_pb2.BarMessage(bar_flag=True),
                    )
                    send_queue.put_nowait(response)

                else:
                    logger.warning(
                        "Received StreamMessage without any known oneof fields."
                    )

        except asyncio.CancelledError:
            logger.info("_recv_loop cancelled (client likely disconnected).")

    async def broadcast_to_all(self, submessage):
        """
        If you want to push a typed submessage to all connected clients,
        you can pass it in, wrap it in a StreamMessage, and queue it.
        """
        # submessage should be one of foo=..., bar=..., or baz=...
        broadcast_msg = racehub_pb2.StreamMessage(**submessage)
        for q in self._connected_clients:
            q.put_nowait(broadcast_msg)


async def serve_grpc(port: int = 50051):
    server = grpc.aio.server()
    servicer = BroadcasterServicer()
    racehub_pb2_grpc.add_BroadcasterServicer_to_server(servicer, server)
    server.add_insecure_port(f"localhost:{port}")

    await server.start()
    logging.info(f"gRPC server started on port {port}")

    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        logging.info("gRPC server cancelled, shutting down.")
        await server.stop(5)

    return servicer
