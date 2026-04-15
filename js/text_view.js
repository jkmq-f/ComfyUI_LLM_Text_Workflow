import { app } from "/scripts/app.js";
import { ComfyWidgets } from "/scripts/widgets.js";

const TARGETS = new Set(["LLMTextView", "LLM Text View"]);

app.registerExtension({
  name: "llm.ShowTextLike",
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    const keys = [nodeData?.name, nodeData?.display_name, nodeType?.comfyClass, nodeType?.title].filter(Boolean);
    if (!keys.some((k) => TARGETS.has(k))) return;

    function populate(text) {
      if (this.widgets) {
        const isConvertedWidget = +!!this.inputs?.[0]?.widget;
        for (let i = isConvertedWidget; i < this.widgets.length; i++) {
          this.widgets[i].onRemove?.();
        }
        this.widgets.length = isConvertedWidget;
      }

      const values = Array.isArray(text) ? [...text] : [text];
      if (!values[0]) values.shift();

      for (let list of values) {
        if (!(list instanceof Array)) list = [list];
        for (const l of list) {
          const w = ComfyWidgets["STRING"](
            this,
            "display_text_" + (this.widgets?.length ?? 0),
            ["STRING", { multiline: true }],
            app
          ).widget;
          w.inputEl.readOnly = true;
          w.inputEl.style.opacity = 0.85;
          w.inputEl.style.minHeight = "180px";
          w.inputEl.style.whiteSpace = "pre-wrap";
          w.inputEl.style.resize = "vertical";
          w.inputEl.style.fontFamily = "monospace";
          w.value = String(l ?? "");
        }
      }

      requestAnimationFrame(() => {
        const sz = this.computeSize();
        if (sz[0] < this.size[0]) sz[0] = this.size[0];
        if (sz[1] < this.size[1]) sz[1] = this.size[1];
        this.onResize?.(sz);
        app.graph.setDirtyCanvas(true, false);
      });
    }

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      populate.call(this, message?.text ?? message?.ui?.text ?? []);
    };

    const VALUES = Symbol();
    const configure = nodeType.prototype.configure;
    nodeType.prototype.configure = function () {
      this[VALUES] = arguments[0]?.widgets_values;
      return configure?.apply(this, arguments);
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      onConfigure?.apply(this, arguments);
      const widgets_values = this[VALUES];
      if (widgets_values?.length) {
        requestAnimationFrame(() => {
          populate.call(this, widgets_values.slice(+(widgets_values.length > 1 && this.inputs?.[0]?.widget)));
        });
      }
    };
  },
});
