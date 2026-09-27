/**
 * FaultLens Frontend - Topology Map Component
 * Interactive HTML5 Canvas microservice dependency graph renderer.
 * Safely renders nodes, traffic pulses, directed arrows, and pulsing red highlights.
 */

window.TopologyMap = {
    canvas: null,
    ctx: null,
    nodes: [],
    dependencies: [],
    hoveredNode: null,

    init(containerId, canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.setupInteractions();
    },

    resize() {
        if (!this.canvas) return;
        const parent = this.canvas.parentElement;
        this.canvas.width = parent.clientWidth;
        this.canvas.height = parent.clientHeight;
        this.render();
    },

    setData(nodes, dependencies) {
        this.dependencies = dependencies || [];
        
        // Auto-layout node positions in radial / multi-tier grid
        const w = this.canvas ? this.canvas.width : 800;
        const h = this.canvas ? this.canvas.height : 450;
        
        const customPositions = {
            'api-gateway': { x: w * 0.12, y: h * 0.45 },
            'auth-service': { x: w * 0.32, y: h * 0.22 },
            'user-db': { x: w * 0.56, y: h * 0.18 },
            'order-service': { x: w * 0.35, y: h * 0.58 },
            'recommendation-engine': { x: w * 0.15, y: h * 0.82 },
            'payment-gateway': { x: w * 0.58, y: h * 0.42 },
            'payment-db': { x: w * 0.86, y: h * 0.25 },
            'third-party-stripe': { x: w * 0.86, y: h * 0.55 },
            'inventory-service': { x: w * 0.58, y: h * 0.82 },
            'inventory-db': { x: w * 0.86, y: h * 0.85 }
        };

        const tierPositions = {
            'gateway': { x: w * 0.15, y: h * 0.5 },
            'auth': { x: w * 0.38, y: h * 0.25 },
            'app': { x: w * 0.48, y: h * 0.55 },
            'database': { x: w * 0.78, y: h * 0.30 },
            'third_party': { x: w * 0.78, y: h * 0.60 }
        };

        const tierCounters = {};

        this.nodes = (nodes || []).map(node => {
            if (customPositions[node.id]) {
                return {
                    ...node,
                    x: customPositions[node.id].x,
                    y: customPositions[node.id].y,
                    radius: 24
                };
            }

            const t = node.tier || 'app';
            tierCounters[t] = (tierCounters[t] || 0) + 1;
            const basePos = tierPositions[t] || { x: w * 0.5, y: h * 0.5 };
            const offset = (tierCounters[t] - 1) * 90;
            return {
                ...node,
                x: basePos.x,
                y: basePos.y + offset,
                radius: 24
            };
        });

        this.render();
    },

    render() {
        if (!this.ctx || !this.canvas) return;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // 1. Draw directed dependency arrows
        this.dependencies.forEach(dep => {
            const srcNode = this.nodes.find(n => n.id === dep.source);
            const tgtNode = this.nodes.find(n => n.id === dep.target);
            if (srcNode && tgtNode) {
                this.drawArrow(ctx, srcNode.x, srcNode.y, tgtNode.x, tgtNode.y, dep.protocol);
            }
        });

        // 2. Draw microservice nodes
        this.nodes.forEach(node => {
            const isCritical = node.health_status === 'CRITICAL';
            const isDegraded = node.health_status === 'DEGRADED';
            
            // Outer glow for critical origin nodes
            if (isCritical) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, node.radius + 10, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(239, 68, 68, 0.3)';
                ctx.fill();

                ctx.beginPath();
                ctx.arc(node.x, node.y, node.radius + 4, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(239, 68, 68, 0.6)';
                ctx.fill();
            }

            // Main node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            ctx.fillStyle = isCritical ? '#ef4444' : (isDegraded ? '#f59e0b' : '#10b981');
            ctx.shadowColor = isCritical ? '#ef4444' : '#10b981';
            ctx.shadowBlur = isCritical ? 15 : 6;
            ctx.fill();
            ctx.shadowBlur = 0;

            // Inner circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius - 4, 0, Math.PI * 2);
            ctx.fillStyle = '#111827';
            ctx.fill();

            // Node Name Label
            ctx.font = '600 11px Inter, sans-serif';
            ctx.fillStyle = '#f3f4f6';
            ctx.textAlign = 'center';
            ctx.fillText(node.name || node.id, node.x, node.y + node.radius + 16);

            // Tier badge
            ctx.font = '400 9px "JetBrains Mono", monospace';
            ctx.fillStyle = isCritical ? '#fca5a5' : '#9ca3af';
            ctx.fillText(`${node.tier.toUpperCase()} | ${node.error_rate_pct || 0}% Err`, node.x, node.y + node.radius + 28);
        });
    },

    drawArrow(ctx, fromX, fromY, toX, toY, protocol) {
        const headlen = 8;
        const dx = toX - fromX;
        const dy = toY - fromY;
        const angle = Math.atan2(dy, dx);
        
        // Offset arrow from node circle edge
        const startX = fromX + 24 * Math.cos(angle);
        const startY = fromY + 24 * Math.sin(angle);
        const endX = toX - 24 * Math.cos(angle);
        const endY = toY - 24 * Math.sin(angle);

        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = '#374151';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Arrow head
        ctx.beginPath();
        ctx.moveTo(endX, endY);
        ctx.lineTo(endX - headlen * Math.cos(angle - Math.PI / 6), endY - headlen * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(endX - headlen * Math.cos(angle + Math.PI / 6), endY - headlen * Math.sin(angle + Math.PI / 6));
        ctx.fillStyle = '#6b7280';
        ctx.fill();
    },

    setupInteractions() {
        if (!this.canvas) return;
        const tooltip = document.getElementById('topology-tooltip');

        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const found = this.nodes.find(n => {
                const dist = Math.hypot(n.x - mouseX, n.y - mouseY);
                return dist <= n.radius;
            });

            if (found && tooltip) {
                tooltip.classList.remove('hidden');
                tooltip.style.left = `${mouseX + 15}px`;
                tooltip.style.top = `${mouseY + 15}px`;
                
                // Safe textContent assignment preventing innerHTML XSS
                tooltip.textContent = '';
                const title = document.createElement('div');
                title.style.fontWeight = '700';
                title.style.color = '#f3f4f6';
                title.textContent = found.name;

                const details = document.createElement('div');
                details.style.color = '#9ca3af';
                details.style.marginTop = '4px';
                details.textContent = `Status: ${found.health_status} | SLA: ${found.sla_latency_ms}ms | P95: ${found.latency_p95_ms || 20}ms`;

                tooltip.appendChild(title);
                tooltip.appendChild(details);
            } else if (tooltip) {
                tooltip.classList.add('hidden');
            }
        });
    }
};
