# ui-sdk: accessible components for Preact

ui-sdk (vercel-labs/ui, Apache-2.0) is a library of unstyled components that
handle keyboard, focus and ARIA for you: dialogs, menus, selects, comboboxes,
tabs, tooltips, toasts, date pickers, sliders, trees and about 40 more.
`assets/ui-sdk/` is a build of its React adapter (`@ui-sdk/react`
0.1.0-beta.10) for Preact 11 through `preact/compat`. It passes 2,868 of the
2,991 tests in ui-sdk's own React suite, where React passes 2,884; the gap is
React-only features (below). Source and test results:
https://github.com/oaustegard/experiments/tree/main/ui-sdk-preact

## When to reach for it

Use a ui-sdk component whenever the UI needs a widget with a WAI-ARIA pattern:
anything that opens (dialog, popover, menu, tooltip, drawer), picks (select,
combobox, listbox, date picker, radio, slider) or navigates (tabs, tree,
toolbar, menubar). Prefer it over hand-rolling the modal, tabs or dropdown in
`assets/component-patterns.md`: focus trapping, Escape, outside presses,
returning focus, typeahead and screen-reader announcements are done and
tested. Hand-roll only display-only pieces (cards, tables, layout).

## Setup

```bash
./scripts/vendor.sh ./vendor --ui-sdk
```

```html
<script type="importmap">
  {
    "imports": {
      "preact": "./vendor/preact.module.js",
      "preact/hooks": "./vendor/hooks.module.js",
      "preact/compat": "./vendor/compat.module.js",
      "preact/jsx-runtime": "./vendor/jsx-runtime.module.js",
      "preact/compat/jsx-runtime": "./vendor/compat-jsx-runtime.module.js",
      "htm": "./vendor/htm.module.js",
      "ui-sdk/": "./vendor/ui-sdk/"
    }
  }
</script>
<style>
  @layer ui-sdk;   /* first line of the page's CSS: ui-sdk's own small layer goes under yours */
</style>
<script type="module">
  import { h, render } from "preact"
  import { useState } from "preact/hooks"
  import htm from "htm"
  import { Dialog, DialogTrigger, DialogBackdrop, DialogContent, DialogTitle,
           DialogDescription, DialogClose } from "ui-sdk/dialog.js"
  const html = htm.bind(h)
  …
</script>
```

Every module path is `ui-sdk/<name>.js`. Import only the components a page
uses: each module loads just its own chunks (button 17 KB gzip, tabs 23 KB,
dialog 43 KB, menu 52 KB, select 60 KB, combobox 62 KB), plus about 11 KB for
Preact and compat.

## Writing parts in HTM

The docs and `scripts/ui_sdk_docs.sh` examples are React TSX. The parts, props,
data attributes and CSS variables are identical in Preact; only the markup
changes. Use `className` as the docs do (compat maps it), or `class`.

```js
// <MenuItem value="new" shortcut="mod+n">New file</MenuItem>
html`<${MenuItem} value="new" shortcut="mod+n">New file<//>`

// render replaces a part's element: <MenuItem render={<a href="/settings" />}>
html`<${MenuItem} render=${html`<a href="/settings" />`}>Settings<//>`

// children as a function of state
html`<${Toggle} aria-label="Mute">${(state) => (state.pressed ? "Mute on" : "Mute off")}<//>`
```

A working page with a menu, a dialog and tabs:

```js
function Demo() {
  const [action, setAction] = useState("")
  return html`
    <${Menu} onAction=${setAction}>
      <${MenuTrigger}>File<//>
      <${MenuContent} className="popup">
        <${MenuItem} className="item" value="new" shortcut="mod+n">New file<//>
        <${MenuItem} className="item" value="save" disabled>Save<//>
        <${MenuSeparator} className="separator" />
        <${MenuCheckboxItem} className="item" value="sidebar" defaultChecked>Show sidebar<//>
        <${MenuSub}>
          <${MenuSubTrigger} className="item">Share<//>
          <${MenuSubContent} className="popup">
            <${MenuItem} className="item" value="email">Email<//>
          <//>
        <//>
      <//>
    <//>
    <output>${action}</output>

    <${Dialog}>
      <${DialogTrigger}>Rename<//>
      <${DialogBackdrop} className="backdrop" />
      <${DialogContent} className="dialog">
        <${DialogTitle}>Rename project<//>
        <${DialogDescription}>Escape closes it; focus returns to Rename.<//>
        <input defaultValue="untitled" />
        <${DialogClose}>Done<//>
      <//>
    <//>

    <${Tabs} defaultValue="a">
      <${TabsList} className="tablist" aria-label="Sections">
        <${TabsTab} className="tab" value="a">Overview<//>
        <${TabsTab} className="tab" value="b">Details<//>
        <${TabsIndicator} className="indicator" />
      <//>
      <${TabsPanel} value="a">First panel<//>
      <${TabsPanel} value="b">Second panel<//>
    <//>`
}
render(html`<${Demo} />`, document.getElementById("app"))
```

## State, events and controllers

- Uncontrolled: `defaultValue`, `defaultOpen`, `defaultChecked`, `defaultPressed`.
- Controlled: `value` + `onValueChange`, `open` + `onOpenChange`, `checked` +
  `onCheckedChange`, `pressed` + `onPressedChange`. Hold the value in `useState`, or pass a signal's `.value` and set it in the callback.
- Every change callback gets `(next, details)`: `details.reason` (such as
  `trigger-press`, `escape-key`, `outside-press`), `details.source`
  (`keyboard`, `mouse`, `touch`, …) and `details.cancel()` to refuse it.
- Nothing selected is `null` (Select, Tabs, Radio); multiple Select and
  Combobox use arrays; Accordion and Toggle Group always use arrays.
- Menus report a chosen item through `onAction(value)`.
- To drive a component from outside its tree (a keyboard shortcut, another
  root), create its controller (`createDialogController()`, listed per
  component below) once, with `useState(() => createDialogController())` or at
  module level, and pass it as `controller=${c}`; then call `c.open()`,
  `c.close()`, `c.setValue()` and so on (each page lists its methods).
- Add `debug` to a root to log each change and its reason to the console.

## Styling

Parts render no styles. Style them by class and by state attributes:

- Every part has `data-slot` (`dialog-content`, `menu-item`, `tabs-tab`, …).
- State: `[data-open]`, `[data-closed]`, `[data-highlighted]` (menu and list
  items), `[data-selected]` (tabs, options), `[data-checked]`, `[data-pressed]`,
  `[data-disabled]`; with values: `[data-side="top"]`, `[data-orientation="vertical"]`.
- Transitions: put enter styles on `[data-starting-style]` and exit styles on
  `[data-ending-style]`; popups stay mounted until the exit finishes.
- Popups set `--anchor-width`, `--available-height` and `--transform-origin`;
  each component's Styling section lists the rest (`ui_sdk_docs.sh <name> --section Styling`).
- `className` and `style` may also be functions of the part's state.

## Preact notes

- Needs Preact 11: the parts take `ref` as a prop, as React 19 does. `vendor.sh` pins 11.2.0.
- Several `render()` roots on one page are fine. The build numbers each root's
  `useId` ids, which stock Preact repeats across roots.
- Not available on Preact: React's `<Activity>` (keeping a hidden page's state)
  and concurrent `useTransition` (Preact's runs synchronously).
- Known issue: after many open/close cycles, the last closed popup's DOM stays
  in memory (one popup's worth, not growing).

## Full docs for a component

```bash
./scripts/ui_sdk_docs.sh --list                       # every page
./scripts/ui_sdk_docs.sh combobox --toc               # headings
./scripts/ui_sdk_docs.sh combobox --section Composition
./scripts/ui_sdk_docs.sh popups                       # a guide: popups, forms, controllers, styling-and-animation
```

Read a component's Composition section before using it for the first time:
it shows which parts nest inside which.

## Components (55)

Each entry: what it is for (the first line of its docs page), the module, and its parts. Fetch the
full page with `scripts/ui_sdk_docs.sh <name>` before building with a component for the first time.

### accordion

Show and hide sections of content from their headings.

`ui-sdk/accordion.js`: `Accordion`, `AccordionHeader`, `AccordionItem`, `AccordionPanel`, `AccordionTrigger`
Controller: `createAccordionController`

### alert-dialog

Ask someone to confirm an action before you continue.

`ui-sdk/alert-dialog.js`: `AlertDialog`, `AlertDialogBackdrop`, `AlertDialogClose`, `AlertDialogContent`, `AlertDialogDescription`, `AlertDialogShortcut`, `AlertDialogTitle`, `AlertDialogTrigger`
Controller: `createAlertDialogController`, `createConfirm`
Also: `confirm`

### autocomplete

Suggest text while someone types, without limiting what they can enter.

`ui-sdk/autocomplete.js`: `Autocomplete`, `AutocompleteArrow`, `AutocompleteClear`, `AutocompleteContent`, `AutocompleteEmpty`, `AutocompleteGroup`, `AutocompleteGroupLabel`, `AutocompleteInput`, `AutocompleteItem`, `AutocompleteItemIcon`, `AutocompleteItemText`, `AutocompleteItems`, `AutocompleteLabel`, `AutocompleteList`, `AutocompleteSeparator`, `AutocompleteStatus`, `AutocompleteTrigger`
Controller: `createAutocompleteController`

### avatar

Show an image with a fallback while it loads or if it fails.

`ui-sdk/avatar.js`: `Avatar`, `AvatarFallback`, `AvatarImage`

### button

Run an action, show that it's working, and keep it reachable when disabled.

`ui-sdk/button.js`: `Button`

### calendar

Choose one date, several dates, or a range from a month grid.

`ui-sdk/calendar.js`: `Calendar`, `CalendarDay`, `CalendarGrid`, `CalendarHeading`, `CalendarMonthSelect`, `CalendarNext`, `CalendarPrevious`, `CalendarWeekday`, `CalendarWeekdays`, `CalendarWeeks`, `CalendarYearSelect`
Controller: `createCalendarController`

### carousel

Page through slides with native scrolling, keyboard controls, and optional rotation.

`ui-sdk/carousel.js`: `Carousel`, `CarouselContent`, `CarouselIndicator`, `CarouselIndicatorGroup`, `CarouselItem`, `CarouselNext`, `CarouselPlayToggle`, `CarouselPrevious`, `CarouselViewport`
Controller: `createCarouselController`

### checkbox

Choose one or more options, individually or as a group.

`ui-sdk/checkbox.js`: `Checkbox`, `CheckboxGroup`, `CheckboxIndicator`
Controller: `createCheckboxController`, `createCheckboxGroupController`

### collapsible

Show and hide a panel, preserve its contents, and animate its height.

`ui-sdk/collapsible.js`: `Collapsible`, `CollapsiblePanel`, `CollapsibleTrigger`
Controller: `createCollapsibleController`

### color-picker

Choose a color by dragging across an area and along sliders, typing any CSS color, or picking a preset.

`ui-sdk/color-picker.js`: `ColorPicker`, `ColorPickerArea`, `ColorPickerAreaCanvas`, `ColorPickerAreaThumb`, `ColorPickerChannelInput`, `ColorPickerEyeDropper`, `ColorPickerInput`, `ColorPickerSlider`, `ColorPickerSliderThumb`, `ColorPickerSwatch`, `ColorPickerSwatchItem`, `ColorPickerSwatches`
Controller: `createColorPickerController`

### combobox

Search a list of options and choose one or several values.

`ui-sdk/combobox.js`: `Combobox`, `ComboboxArrow`, `ComboboxChip`, `ComboboxChipRemove`, `ComboboxChips`, `ComboboxChipsOverflow`, `ComboboxClear`, `ComboboxContent`, `ComboboxCreate`, `ComboboxEmpty`, `ComboboxGroup`, `ComboboxGroupLabel`, `ComboboxInput`, `ComboboxItem`, `ComboboxItemIcon`, `ComboboxItemIndicator`, `ComboboxItemText`, `ComboboxItems`, `ComboboxLabel`, `ComboboxList`, `ComboboxSelectAll`, `ComboboxSeparator`, `ComboboxStatus`, `ComboboxTrigger`, `ComboboxValue`, `ComboboxValueIcon`
Controller: `createComboboxController`

### command

Search commands, run actions, and open pages of more choices.

`ui-sdk/command.js`: `Command`, `CommandEmpty`, `CommandGroup`, `CommandGroupLabel`, `CommandInput`, `CommandItem`, `CommandItemIcon`, `CommandItemText`, `CommandItems`, `CommandList`, `CommandPage`, `CommandSeparator`, `CommandShortcut`, `CommandStatus`
Controller: `createCommandController`

### date-input

Type a date one part at a time, in the order your user's language writes it.

`ui-sdk/date-input.js`: `DateInput`, `DateInputSegment`
Controller: `createDateInputController`

### date-picker

Type a date or choose one from a calendar, with support for ranges and forms.

`ui-sdk/date-picker.js`: `CalendarDay`, `CalendarGrid`, `CalendarHeading`, `CalendarMonthSelect`, `CalendarNext`, `CalendarPrevious`, `CalendarWeekday`, `CalendarWeekdays`, `CalendarWeeks`, `CalendarYearSelect`, `DatePicker`, `DatePickerClear`, `DatePickerContent`, `DatePickerHint`, `DatePickerInput`, `DatePickerPreset`, `DatePickerTrigger`
Controller: `createDatePickerController`

### dialog

Open a focused task over the page.

`ui-sdk/dialog.js`: `Dialog`, `DialogBackdrop`, `DialogClose`, `DialogContent`, `DialogDescription`, `DialogShortcut`, `DialogTitle`, `DialogTrigger`
Controller: `createDialogController`

### drawer

A sheet you can open, drag, and resize from an edge of the screen.

`ui-sdk/drawer.js`: `Drawer`, `DrawerBackdrop`, `DrawerClose`, `DrawerContent`, `DrawerDescription`, `DrawerHandle`, `DrawerOutlet`, `DrawerShortcut`, `DrawerTitle`, `DrawerTrigger`
Controller: `createDrawerController`
Also: `sheetPhysics`

### field

Connect a form control to its label, description, and validation errors.

`ui-sdk/field.js`: `Field`, `FieldControl`, `FieldDescription`, `FieldError`, `FieldGroup`, `FieldLabel`, `FieldLegend`, `FieldSet`
Also: `useFieldControl`

### file-input

Choose, drop, or paste files, validate them, and submit them with a form.

`ui-sdk/file-input.js`: `FileInput`, `FileInputDropzone`, `FileInputItem`, `FileInputItemRemove`, `FileInputList`, `FileInputTrigger`
Controller: `createFileInputController`
Also: `formatFileSize`, `relativePath`

### hover-card

Preview a link on hover or keyboard focus while keeping its normal navigation.

`ui-sdk/hover-card.js`: `HoverCard`, `HoverCardArrow`, `HoverCardContent`, `HoverCardTrigger`
Controller: `createHoverCardController`

### image-cropper

Choose the part of an image to keep by moving and resizing a selection, or by panning and zooming the image under it.

`ui-sdk/image-cropper.js`: `ImageCropper`, `ImageCropperFlip`, `ImageCropperGrid`, `ImageCropperHandle`, `ImageCropperImage`, `ImageCropperRotate`, `ImageCropperSelection`, `ImageCropperViewport`, `ImageCropperZoom`
Controller: `createImageCropperController`

### input

Enter text, add a clear button, and connect the value to your form or state.

`ui-sdk/input.js`: `Input`, `InputClear`, `InputGroup`
Controller: `createInputController`

### label

Name any control with a label, and let a press on the label reach it.

`ui-sdk/label.js`: `Label`

### listbox

Choose one or several options from an always-visible list.

`ui-sdk/listbox.js`: `Listbox`, `ListboxGroup`, `ListboxGroupLabel`, `ListboxItem`, `ListboxItemIcon`, `ListboxItemIndicator`, `ListboxItems`, `ListboxSeparator`
Controller: `createListboxController`

### menu

Choose actions and settings from a button or a context menu.

`ui-sdk/menu.js`: `Menu`, `MenuCheckboxItem`, `MenuContent`, `MenuContextTrigger`, `MenuGroup`, `MenuGroupLabel`, `MenuItem`, `MenuItemIcon`, `MenuItemIndicator`, `MenuItems`, `MenuRadioGroup`, `MenuRadioItem`, `MenuSeparator`, `MenuShortcut`, `MenuSub`, `MenuSubContent`, `MenuSubTrigger`, `MenuTrigger`
Controller: `createMenuController`

### menubar

Move between an application’s menus with one tab stop.

`ui-sdk/menubar.js`: `Menubar`
Controller: `createMenubarController`

### meter

Show a measurement within a known range, such as storage used or an account quota.

`ui-sdk/meter.js`: `Meter`, `MeterIndicator`, `MeterLabel`, `MeterTrack`, `MeterValue`

### navigation-menu

Groups site links into panels that open from a row of triggers.

`ui-sdk/navigation-menu.js`: `NavigationMenu`, `NavigationMenuContent`, `NavigationMenuIndicator`, `NavigationMenuItem`, `NavigationMenuLink`, `NavigationMenuLinkIcon`, `NavigationMenuList`, `NavigationMenuTrigger`, `NavigationMenuViewport`
Controller: `createNavigationMenuController`

### number-input

Enter numbers, step through values, and format them for a locale.

`ui-sdk/number-input.js`: `NumberInput`, `NumberInputControl`, `NumberInputDecrement`, `NumberInputGroup`, `NumberInputIncrement`, `NumberInputScrubArea`, `NumberInputScrubAreaCursor`
Controller: `createNumberInputController`

### otp-input

Enter a one-time code with support for pasting, autofill, and native form validation.

`ui-sdk/otp-input.js`: `OTPInput`, `OTPInputGroup`, `OTPInputSeparator`, `OTPInputSlot`
Controller: `createOTPInputController`

### pagination

Navigate pages with buttons, links, or your router.

`ui-sdk/pagination.js`: `Pagination`, `PaginationEllipsis`, `PaginationFirst`, `PaginationItem`, `PaginationLast`, `PaginationLink`, `PaginationList`, `PaginationNext`, `PaginationPrevious`
Controller: `createPaginationController`
Also: `paginationRange`

### password-input

Enter a password, show or hide it, and use it in a native form.

`ui-sdk/password-input.js`: `PasswordInput`, `PasswordInputControl`, `PasswordInputToggle`
Controller: `createPasswordInputController`

### popover

Edit or explore something beside its trigger.

`ui-sdk/popover.js`: `Popover`, `PopoverArrow`, `PopoverClose`, `PopoverContent`, `PopoverDescription`, `PopoverShortcut`, `PopoverTitle`, `PopoverTrigger`
Controller: `createPopoverController`

### preferences

Apply user preferences to data attributes so your styles can follow them.

`ui-sdk/preferences.js`: `Preferences`
Also: `usePreference`

### progress

Show a task’s progress, or an indeterminate state while its progress is unknown.

`ui-sdk/progress.js`: `Progress`, `ProgressIndicator`, `ProgressLabel`, `ProgressTrack`, `ProgressValue`

### radio

Choose one option, move the selection with arrow keys, and submit it with a form.

`ui-sdk/radio.js`: `Radio`, `RadioGroup`, `RadioIndicator`
Controller: `createRadioGroupController`

### rating

Pick a score from a row of stars, whole or half, with a preview as the pointer moves over them.

`ui-sdk/rating.js`: `Rating`, `RatingItem`
Controller: `createRatingController`

### resizable

Resize, collapse, and save panel layouts with pointer and keyboard controls.

`ui-sdk/resizable.js`: `Resizable`, `ResizableHandle`, `ResizablePanel`
Controller: `createResizableController`
Also: `resizableStorageKey`

### scroll-area

Add styled scrollbars, edge indicators, and follow-to-end behavior to native scrolling.

`ui-sdk/scroll-area.js`: `ScrollArea`, `ScrollAreaContent`, `ScrollAreaCorner`, `ScrollAreaScrollToEnd`, `ScrollAreaScrollbar`, `ScrollAreaThumb`, `ScrollAreaViewport`
Controller: `createScrollAreaController`

### segmented-control

Pick one of a few options from a row of buttons, with an indicator that slides to the choice.

`ui-sdk/segmented-control.js`: `SegmentedControl`, `SegmentedControlIndicator`, `SegmentedControlItem`
Controller: `createSegmentedControlController`

### select

Choose one value or several from a popup list.

`ui-sdk/select.js`: `Select`, `SelectArrow`, `SelectClear`, `SelectContent`, `SelectEmpty`, `SelectGroup`, `SelectGroupLabel`, `SelectInput`, `SelectItem`, `SelectItemIcon`, `SelectItemIndicator`, `SelectItemText`, `SelectItems`, `SelectLabel`, `SelectList`, `SelectSelectAll`, `SelectSeparator`, `SelectStatus`, `SelectTrigger`, `SelectValue`, `SelectValueIcon`
Controller: `createSelectController`

### separator

Divide groups of content with a horizontal or vertical line.

`ui-sdk/separator.js`: `Separator`

### slider

Adjust a number or a range with draggable thumbs and keyboard controls.

`ui-sdk/slider.js`: `Slider`, `SliderControl`, `SliderIndicator`, `SliderThumb`, `SliderTrack`, `SliderValue`
Controller: `createSliderController`

### switch

Turn a setting on or off.

`ui-sdk/switch.js`: `Switch`, `SwitchThumb`
Controller: `createSwitchController`

### tabs

Switch between related panels with one tab selected at a time.

`ui-sdk/tabs.js`: `Tabs`, `TabsIndicator`, `TabsList`, `TabsPanel`, `TabsTab`, `TabsTabIcon`
Controller: `createTabsController`

### textarea

Enter multiple lines of text, grow the field as you type, and connect it to a form.

`ui-sdk/textarea.js`: `Textarea`
Controller: `createInputController`

### time-input

Type a time one part at a time, on the clock your user's language uses.

`ui-sdk/time-input.js`: `TimeInput`, `TimeInputSegment`
Controller: `createTimeInputController`

### timeline

Show dated events in order, like an activity feed, a changelog or an order's progress, with arrow keys between them.

`ui-sdk/timeline.js`: `Timeline`, `TimelineConnector`, `TimelineDescription`, `TimelineItem`, `TimelineMarker`, `TimelineTime`, `TimelineTitle`
Controller: `createTimelineController`

### toast

Show notifications with actions, timed dismissal, and screen reader announcements.

`ui-sdk/toast.js`: `Toast`, `ToastAction`, `ToastClose`, `ToastDescription`, `ToastRegion`, `ToastTitle`
Controller: `createToaster`
Also: `toast`

### toggle

Keep a button pressed, or group toggles with a shared value and arrow-key navigation.

`ui-sdk/toggle.js`: `Toggle`, `ToggleGroup`, `ToggleIcon`
Controller: `createToggleController`, `createToggleGroupController`

### token-input

Mix editable text with tokens for files, people, tags, and other references.

`ui-sdk/token-input.js`: `TokenInput`, `TokenInputEditor`, `TokenInputToken`, `TokenInputTokenRemove`
Controller: `createTokenInputController`
Also: `defaultCodec`, `fromText`, `toLabel`, `toText`

### toolbar

Give buttons, toggles, menus and fields one tab stop with arrow-key navigation.

`ui-sdk/toolbar.js`: `Toolbar`, `ToolbarButton`, `ToolbarGroup`, `ToolbarInput`, `ToolbarLink`, `ToolbarSeparator`
Controller: `createToolbarController`

### tooltip

Name a control or add a short hint on hover and keyboard focus.

`ui-sdk/tooltip.js`: `Tooltip`, `TooltipArrow`, `TooltipContent`, `TooltipShortcut`, `TooltipTrigger`
Controller: `createTooltipController`

### tree

Browse a hierarchy of files, pages, or choices with expandable branches.

`ui-sdk/tree.js`: `Tree`, `TreeGroup`, `TreeItem`, `TreeItemCheckbox`, `TreeItemIndicator`, `TreeItemLabel`, `TreeItems`
Controller: `createTreeController`
Also: `toggleTreeChecked`, `treeCheckedStates`, `treeFromPaths`, `visibleTreeRows`

### trigger-menu

"Opens suggestions at the caret when you type a trigger such as @, /, or #."

`ui-sdk/trigger-menu.js`: `TriggerMenu`, `TriggerMenuContent`, `TriggerMenuEmpty`, `TriggerMenuGroup`, `TriggerMenuGroupLabel`, `TriggerMenuHint`, `TriggerMenuInput`, `TriggerMenuItem`, `TriggerMenuItemIcon`, `TriggerMenuItems`, `TriggerMenuList`, `TriggerMenuSeparator`, `TriggerMenuStatus`
Controller: `createTriggerMenuController`
Also: `textFieldAdapter`

### waterfall

Show a trace or a page's requests as bars on a shared time axis, with spans that expand to show what they started.

`ui-sdk/waterfall.js`: `Waterfall`, `WaterfallAxis`, `WaterfallBar`, `WaterfallCell`, `WaterfallColumnHeader`, `WaterfallHeaderRow`, `WaterfallIndicator`, `WaterfallMark`, `WaterfallRow`, `WaterfallRowHeader`, `WaterfallTick`
Controller: `createWaterfallController`
Also: `visibleWaterfallRows`

## Other modules

Hooks, value helpers and the primitive kit, for building your own parts. 68 `@ui-sdk/core` entry
points are under `ui-sdk/core/` (for example `ui-sdk/core/menu.js`, `ui-sdk/core/agent.js`).

| Module | Exports |
|---|---|
| `agent.js` | `agentTools`, `createAgent`, `registerTools` |
| `async-options.js` | `createAsyncOptions`, `useAsyncOptions` |
| `color.js` | `colorDistance`, `contrastRatio`, `convertColor`, `formatColor`, `isInGamut`, `mixColor`, `parseColor`, `toGamut` |
| `date.js` | `addDays`, `addMonths`, `addYears`, `clampDate`, `dateFormatter`, `dateParts`, `datePattern`, `daysBetween`, `daysInMonth`, `endOfMonth`, `endOfWeek`, `firstDayOfWeek`, `formatDate`, `formatDateRange`, `formatDateToParts`, `isISODate`, `isSameMonth`, `isoDate`, `monthGrid`, `monthNames`, `parseDate`, `startOfMonth`, `startOfWeek`, `toISODate`, `todayDate`, `weekday`, `weekdayNames` |
| `gesture.js` | `createVelocityTracker`, `projectDistance`, `rubberBand`, `sectorOf`, `solveSpring` |
| `history.js` | `createHistory`, `describeEntry`, `stageChanges` |
| `image.js` | `cropImage` |
| `number.js` | `clamp`, `decimalsOf`, `formatNumber`, `formatNumberRange`, `formatNumberToParts`, `fractionOf`, `isPartialNumber`, `maxOnGrid`, `numberFormatter`, `parseNumber`, `roundTo`, `scrubTo`, `stepBy`, `stepFromKey`, `stepValue`, `valueAt`, `wrap` |
| `observe.js` | `elementOf`, `observe`, `withSource` |
| `overlays.js` | `OverlayHost`, `createOverlays`, `overlays` |
| `primitive.js` | `createParts`, `mergeProps`, `renderElement`, `usePart`, `usePrimitive` |
| `shortcuts.js` | `ariaKeyshortcuts`, `formatShortcut`, `registerShortcut`, `shortcuts`, `useShortcut`, `useShortcutHint` |
| `text-match.js` | `fuzzyScore`, `matchRanges`, `matchSegments` |
