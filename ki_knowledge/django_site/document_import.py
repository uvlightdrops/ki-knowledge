"""Django persistence adapter for import-status updates, not content ingestion."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from ki_knowledge.django_site.infosite_models import SourceDocument


logger = logging.getLogger(__name__)


class DjangoImportDocuments:
    def mark_imported(self, project_id: int, document_ids: list[int]) -> int:
        imported = 0
        with transaction.atomic():
            for document_id in document_ids:
                try:
                    document = SourceDocument.objects.select_for_update().get(
                        id=document_id, project_id=project_id,
                    )
                except SourceDocument.DoesNotExist:
                    logger.warning(
                        "Import selection skipped: document %s does not exist in project %s",
                        document_id, project_id,
                    )
                    continue
                if document.import_status != "imported":
                    document.import_status = "imported"
                    document.imported = True
                    document.imported_at = timezone.now()
                    document.save()
                    imported += 1
        return imported
