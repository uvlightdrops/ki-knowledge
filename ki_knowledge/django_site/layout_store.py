from __future__ import annotations

from django.db import transaction

from widgetkit_django.layout_store import LayoutPlacement, LayoutState, LayoutStore

from .infosite_models import DashboardDefinition, DashboardWidgetPlacement, ensure_domain_registered


def subpage_dashboard_slug(area_key: str, subpage_key: str | None, active_domain: str) -> str:
    normalized_subpage = (subpage_key or "").strip().lower().replace("/", "-").replace("_", "-")
    if not normalized_subpage or normalized_subpage == "overview":
        return f"{area_key}-{active_domain}"
    return f"{area_key}-{normalized_subpage}-{active_domain}"


class DjangoDashboardLayoutStore(LayoutStore):
    def _get_dashboard(self, *, area_key: str, subpage_key: str, active_domain: str, owner: object | None, title: str) -> DashboardDefinition | None:
        domain_obj = ensure_domain_registered(active_domain)
        if domain_obj is None:
            raise ValueError(f"Unknown layout domain: {active_domain}")
        dashboard, _ = DashboardDefinition.objects.get_or_create(
            owner=owner,
            domain=domain_obj,
            area_key=area_key,
            slug=subpage_dashboard_slug(area_key, subpage_key, active_domain),
            defaults={"title": title},
        )
        return dashboard

    def _find_dashboard(self, *, area_key: str, subpage_key: str, active_domain: str, owner: object | None) -> DashboardDefinition | None:
        domain_obj = ensure_domain_registered(active_domain)
        if domain_obj is None:
            raise ValueError(f"Unknown layout domain: {active_domain}")
        return (
            DashboardDefinition.objects.filter(
                owner=owner,
                domain=domain_obj,
                area_key=area_key,
                slug=subpage_dashboard_slug(area_key, subpage_key, active_domain),
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )

    def load_placements(self, *, area_key: str, subpage_key: str, active_domain: str, owner: object | None) -> list[LayoutPlacement]:
        return list(self.load_layout(
            area_key=area_key, subpage_key=subpage_key, active_domain=active_domain, owner=owner,
        ).placements)

    def load_layout(self, *, area_key: str, subpage_key: str, active_domain: str, owner: object | None) -> LayoutState:
        dashboard = self._find_dashboard(area_key=area_key, subpage_key=subpage_key, active_domain=active_domain, owner=owner)
        if dashboard is None:
            return LayoutState(exists=False)
        placements = tuple(
            LayoutPlacement(
                widget_id=item.widget_id,
                sort_index=item.sort_index,
                x=item.x,
                y=item.y,
                w=item.w,
                h=item.h,
                config_json=item.config_json,
            )
            for item in DashboardWidgetPlacement.objects.filter(dashboard=dashboard).order_by("sort_index", "widget_id")
        )
        return LayoutState(exists=True, placements=placements)

    def load_shared_placements(self, *, area_key: str, subpage_key: str, active_domain: str) -> list[LayoutPlacement]:
        return self.load_placements(area_key=area_key, subpage_key=subpage_key, active_domain=active_domain, owner=None)

    def load_shared_layout(self, *, area_key: str, subpage_key: str, active_domain: str) -> LayoutState:
        return self.load_layout(area_key=area_key, subpage_key=subpage_key, active_domain=active_domain, owner=None)

    @transaction.atomic
    def replace_placements(
        self,
        *,
        area_key: str,
        subpage_key: str,
        active_domain: str,
        owner: object | None,
        title: str,
        placements: list[LayoutPlacement],
    ) -> None:
        dashboard = self._get_dashboard(
            area_key=area_key,
            subpage_key=subpage_key,
            active_domain=active_domain,
            owner=owner,
            title=title,
        )
        if dashboard is None:
            raise ValueError("Could not resolve a layout for replacement")
        DashboardWidgetPlacement.objects.filter(dashboard=dashboard).delete()
        DashboardWidgetPlacement.objects.bulk_create([
            DashboardWidgetPlacement(
                dashboard=dashboard,
                widget_id=item.widget_id,
                sort_index=item.sort_index,
                x=item.x,
                y=item.y,
                w=item.w,
                h=item.h,
                config_json=item.config_json or {},
            )
            for item in placements
        ])

    def clear_placements(self, *, area_key: str, subpage_key: str, active_domain: str, owner: object | None, title: str) -> None:
        dashboard = self._find_dashboard(
            area_key=area_key,
            subpage_key=subpage_key,
            active_domain=active_domain,
            owner=owner,
        )
        if dashboard is not None:
            dashboard.delete()
