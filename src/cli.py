import click
import redis
import uvicorn

# The server and app objects are defined in src.server
# We need to import them and then assign the created server instance
# to the `server` variable in that module.
from . import server as server_module
from .persistence import RedisPersistence
from .server import RecordReplayServer


@click.command()
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["record", "replay", "mimic", "passthrough"], case_sensitive=False),
    required=True,
    help="The mode to run Proxay in.",
)
@click.option(
    "-h", "--host", type=str, help="The host to proxy to (required in all modes except replay)."
)
@click.option("-p", "--port", type=int, default=3000, help="The local port to serve on.")
@click.option(
    "--default-tape",
    type=str,
    default="default",
    help="Name of the default tape.",
)
@click.option(
    "--redis-host", type=str, default="localhost", help="Redis server host."
)
@click.option("--redis-port", type=int, default=6379, help="Redis server port.")
@click.option(
    "--redis-db", type=int, default=0, help="Redis database number."
)
@click.option(
    "-r",
    "--redact-headers",
    multiple=True,
    help="Request headers to redact (values will be replaced by XXXX). Can be specified multiple times.",
)
def main(mode, host, port, default_tape, redis_host, redis_port, redis_db, redact_headers):
    """
    A Python port of Proxay, a proxy server for recording and replaying HTTP interactions.
    """
    if mode != "replay" and not host:
        raise click.UsageError("A --host must be provided for record, mimic, and passthrough modes.")

    if host and "://" not in host:
        raise click.UsageError("The host must include the scheme (e.g., http:// or https://).")

    click.echo(f"Starting Py-Proxay in {mode} mode on port {port}...")

    # 1. Create Redis and Persistence clients
    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True # Important for working with JSON strings
        )
        # Check connection
        redis_client.ping()
        click.echo(f"Connected to Redis at {redis_host}:{redis_port}/{redis_db}")
    except redis.exceptions.ConnectionError as e:
        raise click.ClickException(f"Could not connect to Redis: {e}")

    persistence = RedisPersistence(redis_client, redact_headers=list(redact_headers))

    # 2. Create the RecordReplayServer instance
    server_instance = RecordReplayServer(
        persistence=persistence,
        initial_mode=mode,
        proxied_host=host,
        default_tape_name=default_tape,
    )

    # 3. Inject the server instance into the server module
    server_module.server = server_instance

    # 4. Run the FastAPI app with uvicorn
    uvicorn.run(server_module.app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
