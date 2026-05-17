/** @odoo-module **/
/**
 * Navbar Theme Service
 * Adds `zyl-sales-advisor-active` to <body> whenever the active Odoo app is
 * "AI Sales Advisor", and removes it when navigating to any other app.
 * Uses a MutationObserver so it works across every view (Dashboard, Analysis,
 * Chat Sessions, Configuration…) without relying on component mount/unmount.
 */
import { registry } from "@web/core/registry";

const APP_BRAND = "AI Sales Advisor";

const zylNavbarThemeService = {
    start() {
        let observer = null;

        const check = () => {
            const brand = document.querySelector(".o_menu_brand");
            if (brand && brand.textContent.trim() === APP_BRAND) {
                document.body.classList.add("zyl-sales-advisor-active");
            } else {
                document.body.classList.remove("zyl-sales-advisor-active");
            }
        };

        const attach = () => {
            const navbar = document.querySelector(".o_main_navbar");
            if (navbar) {
                observer = new MutationObserver(check);
                observer.observe(navbar, {
                    childList: true,
                    subtree: true,
                    characterData: true,
                });
                check();
            } else {
                // Navbar not in DOM yet — retry shortly
                setTimeout(attach, 150);
            }
        };

        attach();

        return {
            destroy() {
                if (observer) observer.disconnect();
                document.body.classList.remove("zyl-sales-advisor-active");
            },
        };
    },
};

registry.category("services").add("zyl_ai_navbar_theme", zylNavbarThemeService);
