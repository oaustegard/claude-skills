# Advanced Chart Patterns

Complete spec structures for specialized charts beyond basic templates.

## Statistical Charts

## Heatmap

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "mark": "rect",
  "encoding": {
    "x": {"field": "category_x", "type": "nominal"},
    "y": {"field": "category_y", "type": "nominal"},
    "color": {
      "field": "value",
      "type": "quantitative",
      "scale": {"scheme": "viridis"}
    },
    "tooltip": [
      {"field": "category_x", "type": "nominal"},
      {"field": "category_y", "type": "nominal"},
      {"field": "value", "type": "quantitative"}
    ]
  }
}
```

## Box Plot

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "mark": {
    "type": "boxplot",
    "extent": "min-max"
  },
  "encoding": {
    "x": {"field": "category", "type": "nominal"},
    "y": {"field": "value", "type": "quantitative"}
  }
}
```

## Violin Plot

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "transform": [
    {
      "density": "value",
      "groupby": ["category"],
      "as": ["value", "density"]
    }
  ],
  "mark": "area",
  "encoding": {
    "x": {
      "field": "density",
      "type": "quantitative",
      "stack": "center",
      "impute": null,
      "axis": null
    },
    "y": {"field": "value", "type": "quantitative"},
    "color": {"field": "category", "type": "nominal"},
    "column": {"field": "category", "type": "nominal"}
  }
}
```

## Waterfall Chart

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "transform": [
    {"window": [{"op": "sum", "field": "amount", "as": "sum"}]},
    {"window": [{"op": "lead", "field": "label", "as": "lead"}]},
    {
      "calculate": "datum.lead === null ? datum.label : datum.lead",
      "as": "lead"
    },
    {
      "calculate": "datum.label === 'Begin' ? 0 : datum.sum - datum.amount",
      "as": "previous_sum"
    },
    {
      "calculate": "datum.label === 'Begin' || datum.label === 'End' ? 0 : datum.amount",
      "as": "amount"
    },
    {
      "calculate": "(datum.label !== 'Begin' && datum.label !== 'End' && datum.amount > 0 ? '+' : '') + datum.amount",
      "as": "text_amount"
    },
    {"calculate": "datum.sum + datum.amount", "as": "sum_end"}
  ],
  "encoding": {"x": {"field": "label", "type": "nominal", "sort": null}},
  "layer": [
    {
      "mark": {"type": "bar", "size": 45},
      "encoding": {
        "y": {"field": "previous_sum", "type": "quantitative"},
        "y2": {"field": "sum"},
        "color": {
          "condition": [
            {"test": "datum.label === 'Begin' || datum.label === 'End'", "value": "#878d96"},
            {"test": "datum.sum < datum.previous_sum", "value": "#d33"}
          ],
          "value": "#24a148"
        }
      }
    }
  ]
}
```

## Sankey Diagram

Use layers to approximate Sankey flow:

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},  // format: [{source, target, value}]
  "transform": [
    {
      "lookup": "source",
      "from": {
        "data": {"values": nodes},  // [{id, order}]
        "key": "id",
        "fields": ["order"]
      },
      "as": ["source_order"]
    },
    {
      "lookup": "target",
      "from": {
        "data": {"values": nodes},
        "key": "id",
        "fields": ["order"]
      },
      "as": ["target_order"]
    }
  ],
  "mark": {"type": "bar", "cornerRadiusEnd": 4},
  "encoding": {
    "x": {"field": "source_order", "type": "ordinal", "axis": null},
    "x2": {"field": "target_order"},
    "y": {"field": "value", "type": "quantitative", "stack": "normalize"},
    "color": {"field": "source", "type": "nominal"}
  }
}
```

## Calendar Heatmap

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},  // format: [{date, value}]
  "transform": [
    {"calculate": "year(datum.date)", "as": "year"},
    {"calculate": "week(datum.date)", "as": "week"},
    {"calculate": "day(datum.date)", "as": "day"}
  ],
  "mark": "rect",
  "encoding": {
    "x": {"field": "week", "type": "ordinal", "title": "Week"},
    "y": {"field": "day", "type": "ordinal", "title": "Day"},
    "color": {
      "field": "value",
      "type": "quantitative",
      "scale": {"scheme": "blues"}
    },
    "facet": {"field": "year", "type": "nominal", "columns": 1},
    "tooltip": [
      {"field": "date", "type": "temporal"},
      {"field": "value", "type": "quantitative"}
    ]
  }
}
```

## Horizon Chart

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "transform": [
    {"calculate": "datum.value > 0 ? datum.value : 0", "as": "positive"},
    {"calculate": "datum.value < 0 ? -datum.value : 0", "as": "negative"}
  ],
  "facet": {"field": "category", "type": "nominal"},
  "spec": {
    "height": 50,
    "layer": [
      {
        "mark": {"type": "area", "clip": true},
        "encoding": {
          "x": {"field": "date", "type": "temporal"},
          "y": {"field": "positive", "type": "quantitative"},
          "color": {"value": "#08519c"}
        }
      },
      {
        "mark": {"type": "area", "clip": true},
        "encoding": {
          "x": {"field": "date", "type": "temporal"},
          "y": {"field": "negative", "type": "quantitative"},
          "color": {"value": "#a50f15"}
        }
      }
    ]
  }
}
```

## Radial Chart (Polar)

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "layer": [
    {
      "mark": {"type": "arc", "innerRadius": 20, "stroke": "#fff"}
    }
  ],
  "encoding": {
    "theta": {"field": "value", "type": "quantitative", "stack": true},
    "radius": {"field": "value", "type": "quantitative", "scale": {"type": "sqrt", "zero": true, "rangeMin": 20}},
    "color": {"field": "category", "type": "nominal"}
  }
}
```

## Bubble Chart with Size Legend

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "mark": "point",
  "encoding": {
    "x": {"field": "x", "type": "quantitative"},
    "y": {"field": "y", "type": "quantitative"},
    "size": {
      "field": "size",
      "type": "quantitative",
      "scale": {"range": [0, 5000]},
      "legend": {"title": "Size"}
    },
    "color": {"field": "category", "type": "nominal"},
    "tooltip": [
      {"field": "name", "type": "nominal"},
      {"field": "x", "type": "quantitative"},
      {"field": "y", "type": "quantitative"},
      {"field": "size", "type": "quantitative"}
    ]
  }
}
```

## Stacked Area with Normalized View

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "mark": "area",
  "encoding": {
    "x": {"field": "date", "type": "temporal"},
    "y": {
      "field": "value",
      "type": "quantitative",
      "stack": "normalize"  // or "center" for streamgraph
    },
    "color": {"field": "category", "type": "nominal"}
  }
}
```

## Error Bars

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "layer": [
    {
      "mark": {"type": "errorbar", "extent": "stdev"},
      "encoding": {
        "x": {"field": "category", "type": "nominal"},
        "y": {"field": "value", "type": "quantitative"}
      }
    },
    {
      "mark": {"type": "point", "filled": true},
      "encoding": {
        "x": {"field": "category", "type": "nominal"},
        "y": {"aggregate": "mean", "field": "value", "type": "quantitative"}
      }
    }
  ]
}
```

## Isotype Grid

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "transform": [
    {
      "window": [{"op": "row_number", "as": "id"}],
      "groupby": ["category"]
    },
    {"calculate": "ceil(datum.id / 10)", "as": "row"},
    {"calculate": "datum.id % 10", "as": "col"}
  ],
  "mark": {"type": "point", "filled": true, "size": 100},
  "encoding": {
    "x": {"field": "col", "type": "ordinal", "axis": null},
    "y": {"field": "row", "type": "ordinal", "axis": null},
    "color": {"field": "category", "type": "nominal"},
    "facet": {"field": "category", "type": "nominal"}
  }
}
```

## Slope Chart

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},  // format: [{category, period, value}]
  "mark": "line",
  "encoding": {
    "x": {"field": "period", "type": "ordinal"},
    "y": {"field": "value", "type": "quantitative"},
    "color": {"field": "category", "type": "nominal"},
    "detail": {"field": "category", "type": "nominal"}
  }
}
```

## Sparklines (Small Multiples)

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": data},
  "facet": {
    "field": "category",
    "type": "nominal",
    "columns": 1
  },
  "spec": {
    "width": 300,
    "height": 30,
    "mark": "line",
    "encoding": {
      "x": {
        "field": "date",
        "type": "temporal",
        "axis": {"title": "", "labels": false}
      },
      "y": {
        "field": "value",
        "type": "quantitative",
        "axis": null,
        "scale": {"zero": false}
      }
    }
  }
}
```
