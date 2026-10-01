import asyncio
import json
import logging
from typing import Any
from sklearn.metrics import (accuracy_score,classification_report,confusion_matrix,
                            f1_score,precision_score,recall_score,)

from src.llm import get_llm_instance
DATASET_PATH = "evals/data/golden_dataset.json"
logger = logging.getLogger(__name__)

FIELDS = ["urgency", "category", "sentiment"]
MAX_CONCURRENCY = 5
REQUEST_TIMEOUT_SECONDS = 60


def load_dataset(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_dict(result: Any) -> dict[str, Any]:
    """Convert a Pydantic v1/v2 model (or plain dict) into a dict."""
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result.dict()


async def classify(
    item: dict[str, Any],
    model: Any,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Classify one test case. Returns (item, result) or (item, None) on failure."""
    item_id = item["id"]

    async with semaphore:
        logger.info("Processing test case %s", item_id)
        try:
            result = await asyncio.wait_for(
                model.chain.ainvoke({"message": item["message"]}),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            result = to_dict(result)

            missing = [f for f in FIELDS if f not in result]
            if missing:
                logger.error("Test case %s missing fields %s in result", item_id, missing)
                return item, None

            logger.info("Result for test case %s: %s", item_id, result)
            return item, result

        except asyncio.TimeoutError:
            logger.error("Test case %s timed out after %ss", item_id, REQUEST_TIMEOUT_SECONDS)
            return item, None
        except Exception:
            logger.exception("Failed to process test case %s", item_id)
            return item, None


def compute_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    labels = sorted(set(y_true) | set(y_pred))
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "report": classification_report(y_true, y_pred, zero_division=0),
        "labels": labels,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels),
    }


def print_metrics(field: str, m: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print(f"{field.upper()} EVALUATION")
    print("=" * 60)
    print(f"Accuracy  : {m['accuracy']:.2%}")
    print(f"Precision : {m['precision']:.2%}")
    print(f"Recall    : {m['recall']:.2%}")
    print(f"F1 Score  : {m['f1']:.2%}")
    print("\nClassification Report:")
    print(m["report"])
    print("Confusion Matrix:")
    print("Labels:", m["labels"])
    print(m["confusion_matrix"])


async def evaluate_classification() -> dict[str, Any]:
    logger.info("Starting classification evaluation")

    dataset = load_dataset(DATASET_PATH)
    logger.info("Loaded %d test cases", len(dataset))

    model = get_llm_instance()

    # Created inside the running loop; safe on all Python versions use for cuncurrency control
    # so only MAX_CONCURRENCY requests are processed at a time to control api overhead.
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    logger.info(
        "Running %d predictions (max %d concurrent)", len(dataset), MAX_CONCURRENCY
    )
    results = await asyncio.gather(
        *(classify(item, model, semaphore) for item in dataset)
    )

    valid = [(item, res) for item, res in results if res is not None]
    failed = len(results) - len(valid)
    logger.info("Completed %d/%d predictions (%d failed)", len(valid), len(results), failed)

    if not valid:
        logger.error("No successful predictions; cannot compute metrics")
        return {"total": len(dataset), "failed": failed, "metrics": {}}

    if failed:
        print(f"\nWARNING: {failed}/{len(results)} test cases failed; "
              f"metrics are computed on the {len(valid)} that succeeded.")

    # Collect results
    expected = {f: [item[f] for item, _ in valid] for f in FIELDS}
    predicted = {f: [res[f] for _, res in valid] for f in FIELDS}

    # Evaluate
    all_metrics: dict[str, Any] = {}
    for field in FIELDS:
        all_metrics[field] = compute_metrics(expected[field], predicted[field])
        print_metrics(field, all_metrics[field])

    logger.info("Classification evaluation completed")
    return {"total": len(dataset), "failed": failed, "metrics": all_metrics}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(evaluate_classification())


# python -m evals.evaluate