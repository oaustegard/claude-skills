# Common Component Patterns

This file contains reusable component patterns that can be copied into projects.

## Data Grid with Sorting

```javascript
import { useSignal, useComputed } from '@preact/signals';
import { html } from 'htm/preact';

function DataGrid({ data, columns }) {
  const sortColumn = useSignal(null);
  const sortDirection = useSignal('asc');

  const sortedData = useComputed(() => {
    if (!sortColumn.value) return data;
    
    const sorted = [...data].sort((a, b) => {
      const aVal = a[sortColumn.value];
      const bVal = b[sortColumn.value];
      
      if (typeof aVal === 'string') {
        return aVal.localeCompare(bVal);
      }
      return aVal - bVal;
    });
    
    return sortDirection.value === 'desc' ? sorted.reverse() : sorted;
  });

  const handleSort = (column) => {
    if (sortColumn.value === column) {
      sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn.value = column;
      sortDirection.value = 'asc';
    }
  };

  return html`
    <div class="overflow-x-auto">
      <table class="min-w-full bg-white border border-gray-300">
        <thead>
          <tr class="bg-gray-100">
            ${columns.map(col => html`
              <th
                key=${col.key}
                onClick=${() => handleSort(col.key)}
                class="px-4 py-2 text-left cursor-pointer hover:bg-gray-200"
              >
                ${col.label}
                ${sortColumn.value === col.key && (
                  sortDirection.value === 'asc' ? ' ↑' : ' ↓'
                )}
              </th>
            `)}
          </tr>
        </thead>
        <tbody>
          ${sortedData.value.map((row, i) => html`
            <tr key=${i} class="border-t hover:bg-gray-50">
              ${columns.map(col => html`
                <td key=${col.key} class="px-4 py-2">
                  ${row[col.key]}
                </td>
              `)}
            </tr>
          `)}
        </tbody>
      </table>
    </div>
  `;
}

// Usage:
// const columns = [
//   { key: 'name', label: 'Name' },
//   { key: 'age', label: 'Age' },
//   { key: 'email', label: 'Email' }
// ];
// html`<${DataGrid} data=${users} columns=${columns} />`;
```

## File Upload with Drag & Drop

```javascript
import { useSignal } from '@preact/signals';
import { html } from 'htm/preact';

function FileUpload({ onFileSelect, accept = '*' }) {
  const isDragging = useSignal(false);
  const files = useSignal([]);

  const handleDragOver = (e) => {
    e.preventDefault();
    isDragging.value = true;
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    isDragging.value = false;
  };

  const handleDrop = (e) => {
    e.preventDefault();
    isDragging.value = false;
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    files.value = droppedFiles;
    onFileSelect?.(droppedFiles);
  };

  const handleFileInput = (e) => {
    const selectedFiles = Array.from(e.target.files);
    files.value = selectedFiles;
    onFileSelect?.(selectedFiles);
  };

  return html`
    <div
      class=${`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
        isDragging.value
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-300 bg-gray-50'
      }`}
      onDragOver=${handleDragOver}
      onDragLeave=${handleDragLeave}
      onDrop=${handleDrop}
    >
      <input
        type="file"
        onChange=${handleFileInput}
        accept=${accept}
        multiple
        class="hidden"
        id="file-input"
      />
      <label for="file-input" class="cursor-pointer">
        <div class="text-gray-600">
          <p class="text-lg font-semibold mb-2">
            Drop files here or click to browse
          </p>
          <p class="text-sm">
            ${accept === '*' ? 'Any file type' : `Accepts: ${accept}`}
          </p>
        </div>
      </label>
      ${files.value.length > 0 && html`
        <div class="mt-4">
          <p class="font-semibold mb-2">Selected files:</p>
          <ul class="text-sm text-left">
            ${files.value.map(file => html`
              <li key=${file.name} class="py-1">
                ${file.name} (${(file.size / 1024).toFixed(1)} KB)
              </li>
            `)}
          </ul>
        </div>
      `}
    </div>
  `;
}

// Usage:
// html`<${FileUpload} 
//   accept=".csv,.json" 
//   onFileSelect=${(files) => console.log(files)}
// />`;
```

## Search with Debouncing

```javascript
import { useSignal, useSignalEffect } from '@preact/signals';
import { html } from 'htm/preact';

function SearchBox({ onSearch, placeholder = 'Search...', debounceMs = 300 }) {
  const query = useSignal('');
  const results = useSignal([]);
  const loading = useSignal(false);

  useSignalEffect(() => {
    const currentQuery = query.value;
    
    if (!currentQuery) {
      results.value = [];
      return;
    }

    loading.value = true;
    const timer = setTimeout(async () => {
      try {
        const data = await onSearch(currentQuery);
        // Only update if query hasn't changed
        if (query.value === currentQuery) {
          results.value = data;
          loading.value = false;
        }
      } catch (error) {
        console.error('Search failed:', error);
        loading.value = false;
      }
    }, debounceMs);

    return () => clearTimeout(timer);
  });

  return html`
    <div class="relative">
      <input
        type="text"
        value=${query}
        onInput=${e => query.value = e.target.value}
        placeholder=${placeholder}
        class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      ${loading.value && html`
        <div class="absolute right-3 top-3">
          <div class="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full"></div>
        </div>
      `}
      ${results.value.length > 0 && html`
        <div class="absolute z-10 w-full mt-2 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          ${results.value.map(result => html`
            <div
              key=${result.id}
              class="px-4 py-2 hover:bg-gray-100 cursor-pointer"
              onClick=${() => {
                query.value = result.name;
                results.value = [];
              }}
            >
              ${result.name}
            </div>
          `)}
        </div>
      `}
    </div>
  `;
}

// Usage:
// const searchUsers = async (query) => {
//   const response = await fetch(`/api/users?q=${query}`);
//   return response.json();
// };
// html`<${SearchBox} onSearch=${searchUsers} />`;
```

## Modal Dialog

```javascript
import { useEffect, useRef } from 'preact/hooks';
import { html } from 'htm/preact';

function Modal({ isOpen, onClose, title, children }) {
  const modalRef = useRef(null);
  const previousFocus = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    // Store previously focused element
    previousFocus.current = document.activeElement;

    // Focus modal
    modalRef.current?.focus();

    // Handle escape key
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);

    // Prevent body scroll
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
      previousFocus.current?.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return html`
    <div
      class="fixed inset-0 z-50 flex items-center justify-center"
      onClick=${onClose}
    >
      <div class="fixed inset-0 bg-black bg-opacity-50"></div>
      <div
        ref=${modalRef}
        tabindex="-1"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        class="relative z-10 bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6"
        onClick=${e => e.stopPropagation()}
      >
        <div class="flex justify-between items-center mb-4">
          <h2 id="modal-title" class="text-xl font-bold">
            ${title}
          </h2>
          <button
            onClick=${onClose}
            aria-label="Close modal"
            class="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>
        <div class="mb-4">
          ${children}
        </div>
      </div>
    </div>
  `;
}

// Usage:
// const isOpen = useSignal(false);
// html`
//   <button onClick=${() => isOpen.value = true}>Open Modal</button>
//   <${Modal}
//     isOpen=${isOpen.value}
//     onClose=${() => isOpen.value = false}
//     title="Confirm Action"
//   >
//     <p>Are you sure you want to proceed?</p>
//     <div class="flex gap-2 mt-4">
//       <button class="px-4 py-2 bg-blue-500 text-white rounded">
//         Confirm
//       </button>
//       <button 
//         onClick=${() => isOpen.value = false}
//         class="px-4 py-2 bg-gray-200 rounded"
//       >
//         Cancel
//       </button>
//     </div>
//   </${Modal}>
// `;
```

## Tabs Component

```javascript
import { useSignal } from '@preact/signals';
import { html } from 'htm/preact';

function Tabs({ tabs }) {
  const activeTab = useSignal(0);

  return html`
    <div class="w-full">
      <div class="flex border-b border-gray-300">
        ${tabs.map((tab, index) => html`
          <button
            key=${index}
            onClick=${() => activeTab.value = index}
            class=${`px-4 py-2 font-medium transition-colors ${
              activeTab.value === index
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            ${tab.label}
          </button>
        `)}
      </div>
      <div class="p-4">
        ${tabs[activeTab.value]?.content}
      </div>
    </div>
  `;
}

// Usage:
// const tabs = [
//   { label: 'Profile', content: html`<div>Profile content</div>` },
//   { label: 'Settings', content: html`<div>Settings content</div>` },
//   { label: 'History', content: html`<div>History content</div>` }
// ];
// html`<${Tabs} tabs=${tabs} />`;
```

## Toast Notifications

```javascript
import { signal } from '@preact/signals';
import { html } from 'htm/preact';

// Global toast state
const toasts = signal([]);

let toastId = 0;

function addToast(message, type = 'info', duration = 3000) {
  const id = toastId++;
  toasts.value = [...toasts.value, { id, message, type }];
  
  if (duration > 0) {
    setTimeout(() => {
      removeToast(id);
    }, duration);
  }
}

function removeToast(id) {
  toasts.value = toasts.value.filter(t => t.id !== id);
}

function ToastContainer() {
  return html`
    <div class="fixed top-4 right-4 z-50 space-y-2">
      ${toasts.value.map(toast => {
        const bgColor = {
          info: 'bg-blue-500',
          success: 'bg-green-500',
          warning: 'bg-yellow-500',
          error: 'bg-red-500'
        }[toast.type] || 'bg-gray-500';

        return html`
          <div
            key=${toast.id}
            class=${`${bgColor} text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-slideIn`}
          >
            <span>${toast.message}</span>
            <button
              onClick=${() => removeToast(toast.id)}
              class="text-white hover:text-gray-200"
            >
              ✕
            </button>
          </div>
        `;
      })}
    </div>
  `;
}

// Usage:
// Add this to your main App component:
// html`<${ToastContainer} />`
// 
// Then call from anywhere:
// addToast('Operation successful!', 'success');
// addToast('Something went wrong', 'error');
```

## CSV Parser Component

```javascript
import { useSignal } from '@preact/signals';
import { html } from 'htm/preact';

function parseCSV(text) {
  const lines = text.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim());
  
  const data = lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim());
    const obj = {};
    headers.forEach((header, i) => {
      obj[header] = values[i];
    });
    return obj;
  });
  
  return { headers, data };
}

function CSVUploader({ onDataParsed }) {
  const status = useSignal('');

  const handleFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    status.value = 'Parsing...';
    
    try {
      const text = await file.text();
      const parsed = parseCSV(text);
      onDataParsed(parsed);
      status.value = `Parsed ${parsed.data.length} rows`;
    } catch (error) {
      status.value = `Error: ${error.message}`;
    }
  };

  return html`
    <div class="space-y-4">
      <input
        type="file"
        accept=".csv"
        onChange=${handleFile}
        class="block w-full text-sm text-gray-500
          file:mr-4 file:py-2 file:px-4
          file:rounded-lg file:border-0
          file:text-sm file:font-semibold
          file:bg-blue-50 file:text-blue-700
          hover:file:bg-blue-100"
      />
      ${status.value && html`
        <p class="text-sm text-gray-600">${status}</p>
      `}
    </div>
  `;
}

// Usage:
// html`<${CSVUploader} 
//   onDataParsed=${({ headers, data }) => {
//     console.log('Headers:', headers);
//     console.log('Data:', data);
//   }}
// />`;
```
