"""Pagination shared by every list endpoint."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page size 25, overridable per request.

    DRF's PageNumberPagination ignores ?page_size= unless the query parameter
    is named here, which fails silently: a caller asking for 500 rows gets 25
    and no indication that the rest exist. Screens that legitimately need the
    whole set - printing ID cards, a roll call, a picker - rely on this.

    max_page_size caps it so the parameter cannot be used to ask the database
    for an entire college in one request.
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 1000
