from google.cloud import bigquery

from app.config import settings


def get_top_headlines(limit: int = 5, min_relevance: float = 0.7) -> list[dict]:
    """Query BigQuery scout_news.items for top recent headlines."""
    client = bigquery.Client(project=settings.gcp_project)

    query = """
        SELECT
            title,
            headline,
            summary,
            so_what,
            relevance_score,
            category,
            areas,
            source_name,
            published_at
        FROM `scout_news.items`
        WHERE relevance_score >= @min_relevance
        ORDER BY published_at DESC
        LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("min_relevance", "FLOAT64", min_relevance),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]


def get_headlines_for_area(area_slug: str, limit: int = 3) -> list[dict]:
    """Query headlines mentioning a specific area."""
    client = bigquery.Client(project=settings.gcp_project)

    # Convert slug to area name (e.g. "dubai-marina" -> "Dubai Marina")
    area_name = area_slug.replace("-", " ").title()

    query = """
        SELECT
            title,
            headline,
            summary,
            so_what,
            relevance_score,
            category,
            source_name,
            published_at
        FROM `scout_news.items`
        WHERE @area_name IN UNNEST(areas)
        ORDER BY published_at DESC
        LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("area_name", "STRING", area_name),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]
