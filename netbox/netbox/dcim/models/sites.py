from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from mptt.models import MPTTModel, TreeForeignKey
from taggit.managers import TaggableManager
from timezone_field import TimeZoneField

from dcim.choices import *
from dcim.constants import *
from dcim.fields import ASNField
from extras.models import ChangeLoggedModel, CustomFieldModel, ObjectChange, TaggedItem
from extras.utils import extras_features
from utilities.fields import NaturalOrderingField
from utilities.querysets import RestrictedQuerySet
from utilities.mptt import TreeManager
from utilities.utils import serialize_object

__all__ = (
    'Region',
    'Site',
)


#
# Regions
#

@extras_features('export_templates', 'webhooks')
class Region(MPTTModel, ChangeLoggedModel):
    """
    Sites can be grouped within geographic Regions.
    """
    parent = TreeForeignKey(
        to='self',
        on_delete=models.CASCADE,
        related_name='children',
        blank=True,
        null=True,
        db_index=True,
        verbose_name='родитель'
    )
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='название'
    )
    slug = models.SlugField(
        unique=True
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='описание'
    )

    objects = TreeManager()

    csv_headers = ['name', 'slug', 'parent', 'description']

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = 'регион'
        verbose_name_plural = 'регионы'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?region={}".format(reverse('dcim:site_list'), self.slug)

    def to_csv(self):
        return (
            self.name,
            self.slug,
            self.parent.name if self.parent else None,
            self.description,
        )

    def get_site_count(self):
        return Site.objects.filter(
            Q(region=self) |
            Q(region__in=self.get_descendants())
        ).count()

    def to_objectchange(self, action):
        # Remove MPTT-internal fields
        return ObjectChange(
            changed_object=self,
            object_repr=str(self),
            action=action,
            object_data=serialize_object(self, exclude=['level', 'lft', 'rght', 'tree_id'])
        )


#
# Sites
#

@extras_features('custom_fields', 'custom_links', 'graphs', 'export_templates', 'webhooks')
class Site(ChangeLoggedModel, CustomFieldModel):
    """
    A Site represents a geographic location within a network; typically a building or campus. The optional facility
    field can be used to include an external designation, such as a data center name (e.g. Equinix SV6).
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='наименование'
    )
    _name = NaturalOrderingField(
        target_field='name',
        max_length=100,
        blank=True
    )
    slug = models.SlugField(
        unique=True
    )
    status = models.CharField(
        max_length=50,
        choices=SiteStatusChoices,
        default=SiteStatusChoices.STATUS_ACTIVE,
        verbose_name='статус'
    )
    region = models.ForeignKey(
        to='dcim.Region',
        on_delete=models.SET_NULL,
        related_name='sites',
        blank=True,
        null=True,
        verbose_name='регион'
    )
    tenant = models.ForeignKey(
        to='tenancy.Tenant',
        on_delete=models.PROTECT,
        related_name='sites',
        blank=True,
        null=True,
        verbose_name='учреждение'
    )
    facility = models.CharField(
        max_length=50,
        blank=True,
        help_text='код региона'
    )
    asn = ASNField(
        blank=True,
        null=True,
        verbose_name='ASN',
        help_text='32-bit автономный номер'
    )
    time_zone = TimeZoneField(
        blank=True,
        verbose_name='часовой пояс'
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='описание'
    )
    physical_address = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='фактический адрес'
    )
    shipping_address = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='адрес доставки'
    )
    latitude = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name='широта',
        help_text='GPS координаты (широта)'
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name='долгота',
        help_text='GPS координаты (долгота)'
    )
    contact_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='ФИО ответственного'
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='контактный телефон'
    )
    contact_email = models.EmailField(
        blank=True,
        verbose_name='электронная почта'
    )
    comments = models.TextField(
        blank=True,
        verbose_name='коментарии'
    )
    custom_field_values = GenericRelation(
        to='extras.CustomFieldValue',
        content_type_field='obj_type',
        object_id_field='obj_id'
    )
    images = GenericRelation(
        to='extras.ImageAttachment',
        verbose_name='изображения'
    )
    tags = TaggableManager(through=TaggedItem)

    objects = RestrictedQuerySet.as_manager()

    csv_headers = [
        'name', 'slug', 'status', 'region', 'tenant', 'facility', 'asn', 'time_zone', 'description', 'physical_address',
        'shipping_address', 'latitude', 'longitude', 'contact_name', 'contact_phone', 'contact_email', 'comments',
    ]
    clone_fields = [
        'status', 'region', 'tenant', 'facility', 'asn', 'time_zone', 'description', 'physical_address',
        'shipping_address', 'latitude', 'longitude', 'contact_name', 'contact_phone', 'contact_email',
    ]

    STATUS_CLASS_MAP = {
        SiteStatusChoices.STATUS_PLANNED: 'info',
        SiteStatusChoices.STATUS_STAGING: 'primary',
        SiteStatusChoices.STATUS_ACTIVE: 'success',
        SiteStatusChoices.STATUS_DECOMMISSIONING: 'warning',
        SiteStatusChoices.STATUS_RETIRED: 'danger',
    }

    class Meta:
        ordering = ('_name',)
        verbose_name = 'адрес'
        verbose_name_plural = 'адреса'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('dcim:site', args=[self.slug])

    def to_csv(self):
        return (
            self.name,
            self.slug,
            self.get_status_display(),
            self.region.name if self.region else None,
            self.tenant.name if self.tenant else None,
            self.facility,
            self.asn,
            self.time_zone,
            self.description,
            self.physical_address,
            self.shipping_address,
            self.latitude,
            self.longitude,
            self.contact_name,
            self.contact_phone,
            self.contact_email,
            self.comments,
        )

    def get_status_class(self):
        return self.STATUS_CLASS_MAP.get(self.status)
