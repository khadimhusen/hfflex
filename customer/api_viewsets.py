from rest_framework import viewsets

from .models import Customer, Address, Person
from .api_serializers import (
    CustomerSerializer, AddressSerializer, PersonSerializer, MarketingUserSerializer,
)
from .filters import CustomerFilter
from .querysets import marketing_users
from .permissions import IsCustomerUser


class MarketingUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = marketing_users()
    serializer_class = MarketingUserSerializer
    permission_classes = [IsCustomerUser]


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('marketing_person', 'createdby', 'editedby')
    serializer_class = CustomerSerializer
    filterset_class = CustomerFilter
    search_fields = ['name', 'gst', 'email']
    permission_classes = [IsCustomerUser]

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.select_related('customer', 'createdby', 'editedby')
    serializer_class = AddressSerializer
    filterset_fields = ['customer']
    permission_classes = [IsCustomerUser]

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.select_related('customer', 'createdby', 'editedby')
    serializer_class = PersonSerializer
    filterset_fields = ['customer']
    permission_classes = [IsCustomerUser]

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)
