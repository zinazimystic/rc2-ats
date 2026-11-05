// Tree-shaken Apache ECharts: only the chart types the dashboard uses are bundled (loaded lazily by <EChart/>).
import * as echarts from "echarts/core";
import { BarChart, FunnelChart, GaugeChart, LineChart, RadarChart, SankeyChart } from "echarts/charts";
import { AriaComponent, GridComponent, RadarComponent, TooltipComponent } from "echarts/components";
import { LabelLayout, UniversalTransition } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  BarChart, LineChart, FunnelChart, GaugeChart, RadarChart, SankeyChart,
  GridComponent, TooltipComponent, RadarComponent, AriaComponent,
  LabelLayout, UniversalTransition, CanvasRenderer,
]);

export { echarts };
