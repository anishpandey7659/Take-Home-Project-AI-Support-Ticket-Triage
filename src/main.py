import asyncio
from .llm import get_llm_instance


get_llm = get_llm_instance()

if __name__ == "__main__":

    async def main() -> None:
        llm = get_llm
        result = await llm.ainvoke(
            "Do you offer a family plan that covers multiple patients under one account?"
        )
        print(result)

    asyncio.run(main())