# crm/pagination.py
from rest_framework.pagination import PageNumberPagination


class CrmPageNumberPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200  # safety cap — stops someone requesting ?page_size=999999