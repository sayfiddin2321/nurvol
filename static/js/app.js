/* ============================================================
   ELECTROPASS — Enterprise SaaS Frontend Core
   Features: Lucide Icons, Dark/Light Mode, Sidebar Drawer,
   Tabs Manager, Lightbox, Auto-dismiss alerts, Confirm dialogs
   ============================================================ */

(function () {
    "use strict";

    // ---------- 1. Lucide Icons Initializer ----------
    function initIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    // ---------- 2. Dark / Light Mode System ----------
    function initTheme() {
        const themeToggleBtns = document.querySelectorAll(".theme-toggle-btn");
        const currentTheme = localStorage.getItem("electropass_theme") || 
            (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

        document.documentElement.setAttribute("data-theme", currentTheme);
        updateThemeIcons(currentTheme);

        themeToggleBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                const active = document.documentElement.getAttribute("data-theme");
                const next = active === "dark" ? "light" : "dark";
                document.documentElement.setAttribute("data-theme", next);
                localStorage.setItem("electropass_theme", next);
                updateThemeIcons(next);
            });
        });
    }

    function updateThemeIcons(theme) {
        document.querySelectorAll(".theme-icon-sun").forEach(el => {
            el.style.display = theme === "dark" ? "block" : "none";
        });
        document.querySelectorAll(".theme-icon-moon").forEach(el => {
            el.style.display = theme === "dark" ? "none" : "block";
        });
    }

    // ---------- 3. Sidebar System (Desktop Collapse + Mobile Drawer) ----------
    function initSidebar() {
        const sidebar = document.querySelector(".sidebar");
        const mainWrapper = document.querySelector(".main-wrapper");
        const desktopToggle = document.querySelector(".sidebar-toggle-btn");
        const mobileToggle = document.querySelector(".header-mobile-toggle");
        const backdrop = document.querySelector(".sidebar-backdrop");

        if (!sidebar) return;

        // Desktop collapse toggle
        if (desktopToggle && mainWrapper) {
            desktopToggle.addEventListener("click", () => {
                sidebar.classList.toggle("collapsed");
                mainWrapper.classList.toggle("sidebar-collapsed");
                const isCollapsed = sidebar.classList.contains("collapsed");
                localStorage.setItem("electropass_sidebar_collapsed", isCollapsed ? "1" : "0");
                initIcons();
            });

            // Restore desktop preference
            if (window.innerWidth > 868 && localStorage.getItem("electropass_sidebar_collapsed") === "1") {
                sidebar.classList.add("collapsed");
                mainWrapper.classList.add("sidebar-collapsed");
            }
        }

        // Mobile drawer toggle
        function openMobileSidebar() {
            sidebar.classList.add("mobile-open");
            if (backdrop) backdrop.classList.add("active");
            document.body.style.overflow = "hidden";
        }

        function closeMobileSidebar() {
            sidebar.classList.remove("mobile-open");
            if (backdrop) backdrop.classList.remove("active");
            document.body.style.overflow = "";
        }

        if (mobileToggle) {
            mobileToggle.addEventListener("click", openMobileSidebar);
        }

        if (backdrop) {
            backdrop.addEventListener("click", closeMobileSidebar);
        }

        // Close drawer on link click in mobile view
        sidebar.querySelectorAll(".sidebar-link").forEach(link => {
            link.addEventListener("click", () => {
                if (window.innerWidth <= 868) {
                    closeMobileSidebar();
                }
            });
        });
    }

    // ---------- 4. Tabs System ----------
    function initTabs() {
        const tabBtns = document.querySelectorAll(".tab-btn[data-tab]");
        if (!tabBtns.length) return;

        document.querySelectorAll(".tabs-navigation").forEach(navigation => {
            const nav = navigation.querySelector(".tabs-nav");
            const scrollButtons = navigation.querySelectorAll("[data-tabs-scroll]");
            if (!nav || !scrollButtons.length) return;

            const updateScrollButtons = () => {
                const maxScroll = nav.scrollWidth - nav.clientWidth;
                navigation.classList.toggle("is-scrollable", maxScroll > 2);
                navigation.classList.toggle("can-scroll-back", nav.scrollLeft > 2);
                navigation.classList.toggle("can-scroll-forward", nav.scrollLeft < maxScroll - 2);
            };

            scrollButtons.forEach(button => {
                button.addEventListener("click", () => {
                    const direction = Number(button.getAttribute("data-tabs-scroll"));
                    nav.scrollBy({
                        left: direction * Math.max(nav.clientWidth * 0.72, 180),
                        behavior: "smooth"
                    });
                });
            });

            nav.addEventListener("scroll", updateScrollButtons, { passive: true });
            window.addEventListener("resize", updateScrollButtons);
            updateScrollButtons();
        });

        tabBtns.forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                const targetId = btn.getAttribute("data-tab");
                const container = btn.closest(".tabs-container") || document;

                // Deactivate all sibling buttons
                const currentNav = btn.closest(".tabs-nav");
                if (currentNav) {
                    currentNav.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
                }
                btn.classList.add("active");

                // Switch panes
                container.querySelectorAll(".tab-pane").forEach(pane => {
                    pane.classList.remove("active");
                });
                const activePane = container.querySelector(`#${targetId}`);
                if (activePane) {
                    activePane.classList.add("active");
                }
                btn.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });

                // If URL hash support needed
                if (window.history.replaceState) {
                    window.history.replaceState(null, null, `#${targetId}`);
                }
            });
        });

        // Sidebar links and browser history can change the hash without reloading.
        function openHashTab() {
        if (window.location.hash && window.location.hash.startsWith("#tab-")) {
            const hashTarget = window.location.hash.slice(1);
            const normalizedTarget = hashTarget.startsWith("tab-tab-")
                ? hashTarget.slice(4)
                : hashTarget;
            const aliases = {"tab-architecture": "tab-technical", "tab-panels": "tab-technical", "tab-circuits": "tab-technical", "tab-cables": "tab-technical", "tab-devices": "tab-technical", "tab-history": "tab-overview", "tab-revisions": "tab-overview"};
            const targetId = aliases[normalizedTarget] || normalizedTarget;
            const section = document.getElementById(normalizedTarget);
            if (section && section.tagName === "DETAILS") section.open = true;
            const matchingBtn = Array.from(tabBtns).find(btn => btn.dataset.tab === targetId);
            if (matchingBtn) {
                matchingBtn.click();
            }
        }
        }
        window.addEventListener("hashchange", openHashTab);
        openHashTab();
    }

    function initWiringPreview() {
        const pages = document.querySelectorAll(".wiring-preview");
        if (!pages.length) return;

        const read = (selector) => {
            const field = document.querySelector(selector);
            if (!field) return "";
            if (field.tagName === "SELECT") {
                return field.selectedOptions[0]?.textContent.trim() || "";
            }
            return field.value.trim();
        };
        const setValue = (key, value, fallback) => {
            const target = document.querySelector(`[data-wiring-value="${key}"]`);
            if (target) target.textContent = value || fallback;
        };
        const update = () => {
            const circuitName = read("#id_name");
            const circuitCode = read("#id_circuit_code");
            const cableType = read("#id_cable_type");
            const cableSize = read("#id_cross_section");
            const cableName = read("#id_name");
            const cableLabel = [cableName, cableType && cableSize ? `${cableType} · ${cableSize}` : cableType || cableSize]
                .filter(Boolean)
                .join(" — ");

            setValue("panel", read("#id_panel"), "Shit tanlang");
            setValue(
                "circuit",
                [circuitCode, circuitName].filter(Boolean).join(" — "),
                "Yangi liniya"
            );
            setValue(
                "load",
                read("#id_description"),
                "Ulanadigan yuklamani izohga yozing"
            );
            setValue("source-circuit", read("#id_circuit"), "Liniya tanlanmagan");
            setValue("cable", cableLabel, "Kabel markasi va kesimi");
            setValue("room", read("#id_room"), "Xona tanlanmagan");
        };

        ["#id_panel", "#id_name", "#id_circuit_code", "#id_description",
            "#id_circuit", "#id_cable_type", "#id_cross_section", "#id_room"]
            .forEach((selector) => {
                const field = document.querySelector(selector);
                if (field) {
                    field.addEventListener("input", update);
                    field.addEventListener("change", update);
                }
            });
        update();
    }

    // ---------- 5. Header User Dropdown ----------
    function initDropdowns() {
        const dropdownTriggers = document.querySelectorAll("[data-dropdown-toggle]");
        
        dropdownTriggers.forEach(trigger => {
            trigger.addEventListener("click", (e) => {
                e.stopPropagation();
                const targetId = trigger.getAttribute("data-dropdown-toggle");
                const menu = document.getElementById(targetId);
                if (menu) {
                    menu.classList.toggle("open");
                }
            });
        });

        document.addEventListener("click", () => {
            document.querySelectorAll(".header-user-dropdown.open, .dropdown-menu.open").forEach(menu => {
                menu.classList.remove("open");
            });
        });
    }

    // ---------- 6. Messages Auto-dismiss ----------
    function initMessages() {
        const messages = document.querySelectorAll(".msg-banner, .msg");
        messages.forEach((msg) => {
            setTimeout(() => {
                msg.style.transition = "opacity 0.4s, transform 0.4s";
                msg.style.opacity = "0";
                msg.style.transform = "translateY(-8px)";
                setTimeout(() => msg.remove(), 400);
            }, 4500);
        });
    }

    // ---------- 7. Confirmation Dialogs ----------
    function initConfirmActions() {
        document.querySelectorAll("[data-confirm]").forEach(element => {
            element.addEventListener("click", (e) => {
                const message = element.getAttribute("data-confirm") || "Ushbu amalni bajarishni tasdiqlaysizmi?";
                if (!window.confirm(message)) {
                    e.preventDefault();
                }
            });
        });
    }

    // Initialize all modules when DOM is ready
    document.addEventListener("DOMContentLoaded", () => {
        initTheme();
        initSidebar();
        initTabs();
        initDropdowns();
        initMessages();
        initConfirmActions();
        initWiringPreview();
        initIcons();
    });

    // Global helper for re-rendering icons after dynamic updates
    window.NURVOLT = window.ElectroPass = {
        refreshIcons: initIcons
    };
})();
