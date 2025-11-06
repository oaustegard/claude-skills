import React, { useState } from 'react';

const ROWS = 'ABCDEFGHIJ'.split('');
const COLS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

// Props will be passed from Claude when generating the artifact
// humanBoard: your ship placements
// humanAttacks: cells you've attacked and their results
// claudeAttacks: cells Claude has attacked (you report results)
export default function BattleshipGame({
  humanBoard = [],
  humanAttacks = {},
  claudeAttacks = {},
  turnNumber = 1,
  humanShipsRemaining = 5,
  claudeShipsRemaining = 5
}) {
  const [selectedCell, setSelectedCell] = useState(null);

  // Create a lookup for human's ships
  const humanShipCells = new Set();
  humanBoard.forEach(ship => {
    ship.cells.forEach(cell => humanShipCells.add(cell));
  });

  const getHumanCellStatus = (cell) => {
    if (claudeAttacks[cell] === 'hit') return 'hit';
    if (claudeAttacks[cell] === 'miss') return 'miss';
    if (humanShipCells.has(cell)) return 'ship';
    return 'empty';
  };

  const getClaudeCellStatus = (cell) => {
    if (humanAttacks[cell] === 'hit') return 'hit';
    if (humanAttacks[cell] === 'miss') return 'miss';
    return 'unknown';
  };

  const getCellColor = (status, isHuman) => {
    if (isHuman) {
      switch (status) {
        case 'hit': return 'bg-red-600';
        case 'miss': return 'bg-blue-300';
        case 'ship': return 'bg-gray-400';
        case 'empty': return 'bg-blue-50';
      }
    } else {
      switch (status) {
        case 'hit': return 'bg-red-600';
        case 'miss': return 'bg-blue-300';
        case 'unknown': return 'bg-blue-50 hover:bg-blue-200 cursor-pointer';
      }
    }
  };

  const getCellContent = (status) => {
    switch (status) {
      case 'hit': return '💥';
      case 'miss': return '○';
      default: return '';
    }
  };

  const handleAttack = (cell) => {
    if (humanAttacks[cell]) return; // Already attacked
    setSelectedCell(cell);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-800 to-slate-900 p-4">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-5xl font-bold text-center mb-4 text-white">
          ⚓ BATTLESHIP
        </h1>

        {/* Game Status */}
        <div className="bg-white rounded-lg shadow-lg p-4 mb-6">
          <div className="flex justify-around items-center">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">{humanShipsRemaining}</div>
              <div className="text-sm text-gray-600">Your Ships</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-gray-800">Turn {turnNumber}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-red-600">{claudeShipsRemaining}</div>
              <div className="text-sm text-gray-600">Claude's Ships</div>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Your Board */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-bold text-center mb-4 text-gray-800">
              Your Waters
            </h2>
            <p className="text-center text-sm text-gray-600 mb-4">
              Claude's attacks on your board
            </p>
            <div className="inline-block border-4 border-gray-700 rounded-lg bg-blue-100 p-2 mx-auto">
              <div className="grid grid-cols-11 gap-1">
                <div></div>
                {COLS.map(col => (
                  <div key={col} className="w-8 h-8 flex items-center justify-center font-bold text-xs">
                    {col}
                  </div>
                ))}
                {ROWS.map((row, rowIdx) => (
                  <React.Fragment key={row}>
                    <div className="w-8 h-8 flex items-center justify-center font-bold text-xs">
                      {row}
                    </div>
                    {COLS.map((col, colIdx) => {
                      const cell = `${row}${col}`;
                      const status = getHumanCellStatus(cell);
                      return (
                        <div
                          key={cell}
                          className={`w-8 h-8 border border-gray-300 flex items-center justify-center text-xs font-bold ${getCellColor(status, true)}`}
                        >
                          {getCellContent(status)}
                        </div>
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>

          {/* Claude's Board (Attacks) */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-bold text-center mb-4 text-gray-800">
              Enemy Waters
            </h2>
            <p className="text-center text-sm text-gray-600 mb-4">
              Click a cell to attack!
            </p>
            <div className="inline-block border-4 border-red-700 rounded-lg bg-blue-100 p-2 mx-auto">
              <div className="grid grid-cols-11 gap-1">
                <div></div>
                {COLS.map(col => (
                  <div key={col} className="w-8 h-8 flex items-center justify-center font-bold text-xs">
                    {col}
                  </div>
                ))}
                {ROWS.map((row, rowIdx) => (
                  <React.Fragment key={row}>
                    <div className="w-8 h-8 flex items-center justify-center font-bold text-xs">
                      {row}
                    </div>
                    {COLS.map((col, colIdx) => {
                      const cell = `${row}${col}`;
                      const status = getClaudeCellStatus(cell);
                      const isSelected = selectedCell === cell;
                      return (
                        <div
                          key={cell}
                          className={`w-8 h-8 border border-gray-300 flex items-center justify-center text-xs font-bold ${
                            isSelected ? 'bg-yellow-300 ring-2 ring-yellow-500' : getCellColor(status, false)
                          }`}
                          onClick={() => status === 'unknown' && handleAttack(cell)}
                        >
                          {getCellContent(status)}
                        </div>
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Attack Selection */}
        {selectedCell && (
          <div className="mt-6 bg-yellow-100 border-2 border-yellow-500 rounded-lg p-6">
            <h3 className="text-2xl font-bold text-center mb-4 text-gray-800">
              🎯 Attack Selected: {selectedCell}
            </h3>
            <p className="text-center text-lg mb-4">
              Copy and paste this into Claude chat to attack:
            </p>
            <div className="bg-white border-2 border-gray-300 rounded p-4 text-center">
              <code className="text-xl font-bold text-blue-600">
                I attack {selectedCell}
              </code>
            </div>
            <button
              onClick={() => {
                navigator.clipboard.writeText(`I attack ${selectedCell}`);
                alert('Copied to clipboard! Paste into Claude chat.');
              }}
              className="mt-4 w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-bold text-lg"
            >
              Copy Attack Command
            </button>
            <button
              onClick={() => setSelectedCell(null)}
              className="mt-2 w-full px-6 py-3 bg-gray-400 text-white rounded-lg hover:bg-gray-500 transition"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Legend */}
        <div className="mt-6 bg-white rounded-lg shadow-lg p-4">
          <h3 className="font-bold text-gray-800 mb-2">Legend:</h3>
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center">
              <div className="w-6 h-6 bg-red-600 border border-gray-300 mr-2"></div>
              <span className="text-sm">💥 Hit</span>
            </div>
            <div className="flex items-center">
              <div className="w-6 h-6 bg-blue-300 border border-gray-300 mr-2"></div>
              <span className="text-sm">○ Miss</span>
            </div>
            <div className="flex items-center">
              <div className="w-6 h-6 bg-gray-400 border border-gray-300 mr-2"></div>
              <span className="text-sm">Your Ships</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
