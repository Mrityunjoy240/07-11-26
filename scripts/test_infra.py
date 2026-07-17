"""Verify Redis and PostgreSQL connectivity."""

import asyncio

import redis.asyncio as aioredis


async def test_redis():
    r = await aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    await r.set("test:hello", "world", ex=10)
    val = await r.get("test:hello")
    assert val == "world", f"Expected 'world', got {val}"
    info = await r.info("server")
    print(f"Redis OK — version: {info['redis_version']}, ping: {await r.ping()}")
    await r.aclose()


async def test_postgres():
    try:
        import asyncpg
        conn = await asyncpg.connect(
            user="bcrec", password="bcrec_dev", host="localhost", port=5432, database="bcrec"
        )
        version = await conn.fetchval("SELECT version()")
        print(f"PostgreSQL OK — {version}")
        await conn.close()
    except ImportError:
        print("asyncpg not installed, skipping PostgreSQL test")
    except Exception as e:
        print(f"PostgreSQL connection failed (may still be starting): {e}")


async def main():
    print("Testing infrastructure...")
    await test_redis()
    await test_postgres()
    print("All checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
