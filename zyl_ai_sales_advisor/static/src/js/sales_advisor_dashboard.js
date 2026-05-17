/** @odoo-module **/
/**
 * Zylentor AI Sales Advisor — Main Dashboard Component
 * Odoo 17 / OWL 2  •  Chart.js 4
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    Component,
    onMounted,
    onWillUnmount,
    useState,
    useRef,
} from "@odoo/owl";

/* global Chart */

// ── Palette ──────────────────────────────────────────────────────────────────
const PALETTE = [
    "#4F81BD","#C0504D","#9BBB59","#8064A2",
    "#4BACC6","#F79646","#2C4770","#8B2027",
    "#5C7A29","#593F62",
];
const SEASON_COLORS = { Spring:"#9BBB59", Summer:"#F79646", Autumn:"#C0504D", Winter:"#4BACC6" };

function shortNum(val, currency="$") {
    if (val >= 1_000_000) return `${currency}${(val/1_000_000).toFixed(1)}M`;
    if (val >= 1_000)     return `${currency}${(val/1_000).toFixed(1)}K`;
    return `${currency}${val.toFixed(0)}`;
}

// ════════════════════════════════════════════════════════════════════════════
class SalesAdvisorDashboard extends Component {
    static template = "zyl_ai_sales_advisor.Dashboard";

    setup() {
        this.notification = useService("notification");
        this.action       = useService("action");

        this.refTopProducts = useRef("canvasTopProducts");
        this.refMonthly     = useRef("canvasMonthly");
        this.refDoughnut    = useRef("canvasDoughnut");
        this.refSeasonal    = useRef("canvasSeasonal");
        this.chatEndRef     = useRef("chatEnd");
        this.chatPanelRef   = useRef("chatPanel");
        this._charts = {};

        this.state = useState({
            loading: true, error: null,
            dateFrom: this._defaultDateFrom(),
            dateTo: new Date().toISOString().split("T")[0],
            activePeriod: "1y",
            kpis: {}, topProducts: [], monthlyRevenue: [],
            seasonal: { seasons:[], products:[] },
            categories: [], savedInsights: [], currency: "$",
            chatOpen: false, chatSessionId: null, chatMessages: [],
            chatInput: "", chatLoading: false,
            insightGenerating: false, insightType: "sales_overview",
            expandedHelp: {},
        });

        onMounted(async () => {
            await this._loadDashboard();
        });
        onWillUnmount(() => {
            this._destroyAllCharts();
        });
    }

    _defaultDateFrom() {
        const d = new Date(); d.setFullYear(d.getFullYear()-1);
        return d.toISOString().split("T")[0];
    }

    async _loadDashboard() {
        this.state.loading = true; this.state.error = null;
        try {
            const params = new URLSearchParams({ date_from: this.state.dateFrom, date_to: this.state.dateTo });
            const resp = await fetch(`/zyl_ai_sales/api/dashboard?${params}`);
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || "Failed to load dashboard.");
            this.state.kpis           = data.kpis || {};
            this.state.topProducts    = data.top_products || [];
            this.state.monthlyRevenue = data.monthly_revenue || [];
            this.state.seasonal       = data.seasonal || { seasons:[], products:[] };
            this.state.categories     = data.categories || [];
            this.state.savedInsights  = data.saved_insights || [];
            this.state.currency       = data.currency || "$";
        } catch(err) { this.state.error = err.message; }
        finally {
            this.state.loading = false;
            setTimeout(() => this._renderAllCharts(), 80);
        }
    }

    _destroyAllCharts() {
        Object.values(this._charts).forEach(c => { try { c.destroy(); } catch(_){} });
        this._charts = {};
    }

    _makeChart(key, canvas, config) {
        if (this._charts[key]) { this._charts[key].destroy(); delete this._charts[key]; }
        if (!canvas) return;
        this._charts[key] = new Chart(canvas, config);
    }

    _renderAllCharts() {
        if (typeof Chart === "undefined") { console.error("Chart.js not loaded"); return; }
        this._renderTopProducts();
        this._renderMonthly();
        this._renderDoughnut();
        this._renderSeasonal();
    }

    _renderTopProducts() {
        const canvas = this.refTopProducts.el; if (!canvas) return;
        const currency = this.state.currency;
        const labels = this.state.topProducts.map(p => p.product_name || "");
        const values = this.state.topProducts.map(p => p.revenue || 0);
        this._makeChart("topProducts", canvas, {
            type: "bar",
            data: { labels, datasets: [{ label:"Revenue", data:values,
                backgroundColor: PALETTE.map(c=>c+"CC"), borderColor:PALETTE,
                borderWidth:1.5, borderRadius:6, borderSkipped:false }] },
            options: {
                indexAxis: "y", responsive:true, maintainAspectRatio:false,
                plugins: {
                    legend:{ display:false },
                    tooltip:{ callbacks:{ label:ctx=>` ${shortNum(ctx.raw,currency)}` } },
                },
                scales: {
                    x:{ ticks:{ callback:v=>shortNum(v,currency), font:{size:11} }, grid:{color:"#F3F4F6"} },
                    y:{ ticks:{ font:{size:11} }, grid:{display:false} },
                },
            },
        });
    }

    _renderMonthly() {
        const canvas = this.refMonthly.el; if (!canvas) return;
        const currency = this.state.currency;
        const labels = this.state.monthlyRevenue.map(m => m.month);
        const values = this.state.monthlyRevenue.map(m => m.revenue || 0);
        this._makeChart("monthly", canvas, {
            type: "line",
            data: { labels, datasets: [{ label:"Revenue", data:values,
                borderColor:PALETTE[0], backgroundColor:PALETTE[0]+"22",
                borderWidth:2.5, pointRadius:4, pointHoverRadius:6,
                pointBackgroundColor:PALETTE[0], fill:true, tension:0.35 }] },
            options: {
                responsive:true, maintainAspectRatio:false,
                plugins: {
                    legend:{ display:false },
                    tooltip:{ callbacks:{ label:ctx=>` ${shortNum(ctx.raw,currency)}` } },
                },
                scales: {
                    x:{ ticks:{ font:{size:11} }, grid:{color:"#F3F4F6"} },
                    y:{ ticks:{ callback:v=>shortNum(v,currency), font:{size:11} }, grid:{color:"#F3F4F6"} },
                },
            },
        });
    }

    _renderDoughnut() {
        const canvas = this.refDoughnut.el; if (!canvas) return;
        const currency = this.state.currency;
        const labels = this.state.categories.map(c => c.category_name || "");
        const values = this.state.categories.map(c => c.revenue || 0);
        const total  = values.reduce((a,b)=>a+b,0);
        this._makeChart("doughnut", canvas, {
            type: "doughnut",
            data: { labels, datasets:[{ data:values,
                backgroundColor:PALETTE.map(c=>c+"CC"),
                borderColor:"#fff", borderWidth:3, hoverOffset:8 }] },
            options: {
                responsive:true, maintainAspectRatio:false, cutout:"62%",
                plugins: {
                    legend:{ position:"right", labels:{ font:{size:12}, padding:14,
                        generateLabels(chart) {
                            const ds = chart.data.datasets[0];
                            return chart.data.labels.map((lbl,i) => ({
                                text: `${lbl} (${total>0?((ds.data[i]/total)*100).toFixed(1):0}%)`,
                                fillStyle: ds.backgroundColor[i],
                                strokeStyle: "#fff", lineWidth:1, index:i,
                            }));
                        },
                    }},
                    tooltip:{ callbacks:{ label:ctx=>{
                        const pct = total>0?((ctx.raw/total)*100).toFixed(1):0;
                        return ` ${shortNum(ctx.raw,currency)}  (${pct}%)`;
                    }}},
                },
            },
            plugins: [{
                id:"centerText",
                afterDraw(chart) {
                    const { ctx, chartArea:{left,top,right,bottom} } = chart;
                    const cx=(left+right)/2, cy=(top+bottom)/2;
                    ctx.save();
                    ctx.textAlign="center"; ctx.textBaseline="middle";
                    ctx.fillStyle="#1F2937"; ctx.font="bold 16px Inter,sans-serif";
                    ctx.fillText(shortNum(total,currency), cx, cy-10);
                    ctx.fillStyle="#9CA3AF"; ctx.font="12px Inter,sans-serif";
                    ctx.fillText("Total", cx, cy+12);
                    ctx.restore();
                },
            }],
        });
    }

    _renderSeasonal() {
        const canvas = this.refSeasonal.el; if (!canvas) return;
        const currency = this.state.currency;
        const { seasons, products } = this.state.seasonal;
        if (!products || !products.length) return;
        const top5    = products.slice(0,5);
        const labels  = top5.map(p => p.product_name);
        const datasets = (seasons||[]).map(season => ({
            label: season, data: top5.map(p=>(p.data&&p.data[season])||0),
            backgroundColor: (SEASON_COLORS[season]||PALETTE[0])+"CC",
            borderColor: SEASON_COLORS[season]||PALETTE[0],
            borderWidth:1.5, borderRadius:4,
        }));
        this._makeChart("seasonal", canvas, {
            type:"bar", data:{ labels, datasets },
            options: {
                responsive:true, maintainAspectRatio:false,
                plugins: {
                    legend:{ position:"bottom", labels:{ font:{size:12}, padding:14 } },
                    tooltip:{ callbacks:{ label:ctx=>` ${ctx.dataset.label}: ${shortNum(ctx.raw,currency)}` } },
                },
                scales: {
                    x:{ ticks:{ font:{size:10}, maxRotation:20 }, grid:{display:false} },
                    y:{ ticks:{ callback:v=>shortNum(v,currency), font:{size:11} }, grid:{color:"#F3F4F6"} },
                },
            },
        });
    }

    onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        this.state.activePeriod = "custom";
        this._loadDashboard();
    }
    onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        this.state.activePeriod = "custom";
        this._loadDashboard();
    }
    async onRefresh() { await this._loadDashboard(); }
    onSetPeriod(period) {
        const today = new Date();
        const fmt = d => d.toISOString().split("T")[0];
        const ago = days => { const d = new Date(today); d.setDate(d.getDate() - days); return d; };
        const monthStart = (offset=0) => {
            const d = new Date(today.getFullYear(), today.getMonth() - offset, 1);
            return d;
        };
        const monthEnd = (offset=0) => {
            const d = new Date(today.getFullYear(), today.getMonth() - offset + 1, 0);
            return d;
        };
        this.state.activePeriod = period;
        if (period === "30d")  { this.state.dateFrom = fmt(ago(30));  this.state.dateTo = fmt(today); }
        if (period === "90d")  { this.state.dateFrom = fmt(ago(90));  this.state.dateTo = fmt(today); }
        if (period === "6m")   { this.state.dateFrom = fmt(ago(182)); this.state.dateTo = fmt(today); }
        if (period === "1y")   { this.state.dateFrom = fmt(ago(365)); this.state.dateTo = fmt(today); }
        if (period === "mtd")  { this.state.dateFrom = fmt(monthStart(0)); this.state.dateTo = fmt(today); }
        if (period === "ytd")  { this.state.dateFrom = fmt(new Date(today.getFullYear(), 0, 1)); this.state.dateTo = fmt(today); }
        if (period !== "custom") this._loadDashboard();
    }
    toggleHelp(panelId)  { this.state.expandedHelp[panelId] = !this.state.expandedHelp[panelId]; }
    isHelpOpen(panelId)  { return !!this.state.expandedHelp[panelId]; }

    onChatResizeStart(ev) {
        ev.preventDefault();
        const panel = this.chatPanelRef.el;
        if (!panel) return;
        const handle = ev.currentTarget;
        handle.classList.add("dragging");
        // Disable transition during drag so it feels instant
        panel.style.transition = "none";
        const startX = ev.clientX;
        const startW = panel.offsetWidth;
        const maxW = Math.round(window.innerWidth * 0.9);
        const onMove = (e) => {
            const newW = Math.min(Math.max(startW + (startX - e.clientX), 280), maxW);
            // Direct DOM update — no OWL re-render
            panel.style.width = newW + "px";
        };
        const onUp = () => {
            handle.classList.remove("dragging");
            panel.style.transition = "";
            // Commit final width to state once
            this.state.chatWidth = parseInt(panel.style.width, 10) || startW;
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    }

    toggleChat() {
        this.state.chatOpen = !this.state.chatOpen;
        if (this.state.chatOpen && !this.state.chatMessages.length) {
            this.state.chatMessages.push({ role:"assistant", id:"welcome",
                content:"Hello! I'm your AI Sales Advisor. Ask me anything about your sales performance, top products, seasonal trends, or growth strategies. 📊" });
        }
    }
    onChatInputChange(ev) { this.state.chatInput = ev.target.value; }
    async onChatKeydown(ev) {
        if (ev.key==="Enter" && !ev.shiftKey) { ev.preventDefault(); await this._sendChatMessage(); }
    }
    async onChatSend() { await this._sendChatMessage(); }

    async _sendChatMessage() {
        const msg = (this.state.chatInput||"").trim();
        if (!msg || this.state.chatLoading) return;
        this.state.chatMessages.push({ role:"user", content:msg, id:Date.now() });
        this.state.chatInput=""; this.state.chatLoading=true;
        this._scrollChatToBottom();
        try {
            const resp = await fetch("/zyl_ai_sales/api/chat", {
                method:"POST",
                headers:{ "Content-Type":"application/json", "X-CSRF-Token":this._getCsrfToken() },
                body: JSON.stringify({ message:msg, session_id:this.state.chatSessionId,
                    date_from:this.state.dateFrom, date_to:this.state.dateTo }),
            });
            const data = await resp.json();
            if (data.success) {
                this.state.chatSessionId = data.session_id;
                this.state.chatMessages.push({ role:"assistant", content:data.reply, id:Date.now()+1 });
            } else {
                this.state.chatMessages.push({ role:"assistant", isError:true, id:Date.now()+1,
                    content:`⚠️ ${data.error||"Something went wrong."}` });
            }
        } catch {
            this.state.chatMessages.push({ role:"assistant", isError:true, id:Date.now()+1,
                content:"⚠️ Network error. Please check your connection." });
        } finally { this.state.chatLoading=false; this._scrollChatToBottom(); }
    }

    _scrollChatToBottom() {
        setTimeout(() => { if (this.chatEndRef.el) this.chatEndRef.el.scrollIntoView({behavior:"smooth"}); }, 50);
    }
    _getCsrfToken() {
        return document.cookie.split("; ").find(r=>r.startsWith("csrf_token="))?.split("=")[1]||"";
    }

    async onGenerateInsight() {
        if (this.state.insightGenerating) return;
        this.state.insightGenerating = true;
        try {
            const resp = await fetch("/zyl_ai_sales/api/generate_insight", {
                method:"POST",
                headers:{ "Content-Type":"application/json", "X-CSRF-Token":this._getCsrfToken() },
                body: JSON.stringify({ insight_type:this.state.insightType,
                    date_from:this.state.dateFrom, date_to:this.state.dateTo }),
            });
            const data = await resp.json();
            if (data.success) {
                this.notification.add("Insight generated and saved!", { type:"success", title:"AI Insight Ready" });
                await this._loadDashboard();
            } else {
                this.notification.add(data.error||"Failed to generate insight.", { type:"danger", title:"Error" });
            }
        } catch { this.notification.add("Network error while generating insight.", { type:"danger" }); }
        finally { this.state.insightGenerating=false; }
    }
    onInsightTypeChange(ev) { this.state.insightType = ev.target.value; }

    openInsights()     { this.action.doAction("zyl_ai_sales_advisor.action_sales_insights"); }
    openInsightRecord(insightId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "zyl.sales.insight",
            res_id: insightId,
            views: [[false, "form"]],
            target: "current",
        });
    }
    openKpiDrilldown(kpiType) {
        const dateFrom = this.state.dateFrom;
        const dateTo   = this.state.dateTo;
        const domain = [
            ["state", "in", ["sale", "done"]],
            ["date_order", ">=", dateFrom + " 00:00:00"],
            ["date_order", "<=", dateTo   + " 23:59:59"],
        ];
        if (kpiType === "customers") {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Customers",
                res_model: "res.partner",
                domain: [
                    ["sale_order_ids.state", "in", ["sale", "done"]],
                    ["sale_order_ids.date_order", ">=", dateFrom + " 00:00:00"],
                    ["sale_order_ids.date_order", "<=", dateTo   + " 23:59:59"],
                ],
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
        } else {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Sale Orders",
                res_model: "sale.order",
                domain,
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
        }
    }
    openChatSessions() { this.action.doAction("zyl_ai_sales_advisor.action_ai_chat_sessions"); }
    openConfig()       { this.action.doAction("zyl_ai_sales_advisor.action_ai_config"); }

    get growthClass() {
        const g=this.state.kpis.growth_pct||0;
        return g>0?"text-success":g<0?"text-danger":"text-muted";
    }
    get growthIcon() {
        const g=this.state.kpis.growth_pct||0;
        return g>0?"▲":g<0?"▼":"—";
    }
    formatCurrency(val) {
        const c=this.state.currency||"$";
        if(!val&&val!==0) return `${c}0`;
        if(val>=1_000_000) return `${c}${(val/1_000_000).toFixed(2)}M`;
        if(val>=1_000)     return `${c}${(val/1_000).toFixed(1)}K`;
        return `${c}${val.toFixed(2)}`;
    }
    formatNumber(val) {
        if(!val&&val!==0) return "0";
        return new Intl.NumberFormat().format(Math.round(val));
    }
    getSeasonIcon(season) {
        return ({Spring:"🌸",Summer:"☀️",Autumn:"🍂",Winter:"❄️"})[season]||"📊";
    }
    getInsightIcon(type) {
        return ({top_product:"🏆",seasonal:"🌿",revenue_trend:"📈",category:"🗂️",
            growth:"🚀",recommendation:"💡",forecast:"🔮",general:"📊"})[type]||"📊";
    }
    getPriorityClass(priority) {
        return priority==="2"?"insight-critical":priority==="1"?"insight-important":"";
    }
    _heatClass(prod, season) {
        const val=((prod.data&&prod.data[season])||0);
        const values=Object.values(prod.data||{}).filter(v=>v>0);
        if(!values.length||val===0) return "heat-zero";
        const ratio=val/Math.max(...values);
        return ratio>=0.85?"heat-high":ratio>=0.5?"heat-medium":"heat-low";
    }
}

registry.category("actions").add("zyl_ai_sales_advisor.Dashboard", SalesAdvisorDashboard);
