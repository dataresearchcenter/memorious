from banal import ensure_list
from ftmq.store.fragments import get_fragments as get_ftmstore_dataset
from ftmq.store.fragments.settings import Settings as FtmSettings

from memorious.operations import register
from memorious.operations.aleph import get_api

ORIGIN = "memorious"

ftm_settings = FtmSettings()


def get_dataset(context, origin=ORIGIN):
    name = context.get("dataset", context.crawler.name)
    origin = context.get("dataset", origin)
    # Use ftmq's own database_uri setting (FTM_STORE_URI env var)
    return get_ftmstore_dataset(
        name, database_uri=ftm_settings.database_uri, origin=origin
    )


@register("ftm_store")
@register("balkhash_put")  # Legacy alias
def ftm_store(context, data):
    """Store an entity or a list of entities to an ftm store."""
    # This is a simplistic implementation of a balkhash memorious operation.
    # It is meant to serve the use of OCCRP where we pipe data into postgresql.
    dataset = get_dataset(context)
    bulk = dataset.bulk()
    entities = ensure_list(data.get("entities", data))
    for entity in entities:
        context.log.debug(
            "Store entity", schema=entity.get("schema"), id=entity.get("id")
        )
        bulk.put(entity, entity.pop("fragment", None))
        context.emit(rule="fragment", data=data, optional=True)
    context.emit(data=data, optional=True)
    bulk.flush()


@register("ftm_load_aleph")
def ftm_load_aleph(context, data):
    """Write each entity from an ftm store to Aleph via the _bulk API."""
    api = get_api(context)
    if api is None:
        return
    foreign_id = context.params.get("foreign_id", context.crawler.name)
    collection = api.load_collection_by_foreign_id(foreign_id, {})
    collection_id = collection.get("id")
    unsafe = context.params.get("unsafe", False)
    entities = get_dataset(context)
    api.write_entities(collection_id, entities, unsafe=unsafe)
