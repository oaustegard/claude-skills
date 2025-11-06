import React, { useState } from 'react';

const ROWS = 'ABCDEFGHIJ'.split('');
const COLS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

const SHIPS = [
  { name: 'Carrier', length: 5, color: 'bg-red-500' },
  { name: 'Battleship', length: 4, color: 'bg-orange-500' },
  { name: 'Cruiser', length: 3, color: 'bg-yellow-500' },
  { name: 'Submarine', length: 3, color: 'bg-green-500' },
  { name: 'Destroyer', length: 2, color: 'bg-blue-500' },
];

export default function BattleshipSetup() {
  const [board, setBoard] = useState(Array(10).fill(null).map(() => Array(10).fill(null)));
  const [currentShip, setCurrentShip] = useState(0);
  const [orientation, setOrientation] = useState('horizontal');
  const [hovering, setHovering] = useState(null);
  const [placed, setPlaced] = useState([]);
  const [showOutput, setShowOutput] = useState(false);

  const ship = SHIPS[currentShip];

  const canPlaceShip = (row, col) => {
    if (currentShip >= SHIPS.length) return false;

    const cells = [];
    for (let i = 0; i < ship.length; i++) {
      const r = orientation === 'horizontal' ? row : row + i;
      const c = orientation === 'horizontal' ? col + i : col;

      if (r >= 10 || c >= 10) return false;
      if (board[r][c] !== null) return false;

      cells.push([r, c]);
    }
    return cells;
  };

  const placeShip = (row, col) => {
    const cells = canPlaceShip(row, col);
    if (!cells) return;

    const newBoard = board.map(r => [...r]);
    const shipCells = cells.map(([r, c]) => {
      newBoard[r][c] = currentShip;
      return `${ROWS[r]}${c + 1}`;
    });

    setBoard(newBoard);
    setPlaced([...placed, {
      name: ship.name,
      length: ship.length,
      cells: shipCells,
      hits: []
    }]);
    setCurrentShip(currentShip + 1);
    setHovering(null);
  };

  const reset = () => {
    setBoard(Array(10).fill(null).map(() => Array(10).fill(null)));
    setCurrentShip(0);
    setPlaced([]);
    setShowOutput(false);
  };

  const getHoverCells = (row, col) => {
    const cells = canPlaceShip(row, col);
    return cells ? cells.map(([r, c]) => `${r}-${c}`) : [];
  };

  const exportJSON = () => {
    return JSON.stringify(placed, null, 2);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(exportJSON());
    alert('Ship placements copied! Paste this into Claude chat.');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-blue-700 p-8">
      <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-2xl p-8">
        <h1 className="text-4xl font-bold text-center mb-2 text-blue-900">
          ⚓ Battleship Setup
        </h1>
        <p className="text-center text-gray-600 mb-6">
          Place your ships on the board. Click a cell to place your ship.
        </p>

        {/* Current Ship */}
        {currentShip < SHIPS.length ? (
          <div className="mb-6 bg-blue-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-blue-900">
                  Placing: {ship.name}
                </h2>
                <p className="text-gray-600">Length: {ship.length} cells</p>
              </div>
              <button
                onClick={() => setOrientation(orientation === 'horizontal' ? 'vertical' : 'horizontal')}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                Rotate ({orientation})
              </button>
            </div>
          </div>
        ) : (
          <div className="mb-6 bg-green-50 p-4 rounded-lg">
            <h2 className="text-xl font-bold text-green-900 text-center">
              ✅ All ships placed!
            </h2>
          </div>
        )}

        {/* Board */}
        <div className="mb-6 overflow-x-auto">
          <div className="inline-block border-4 border-blue-900 rounded-lg bg-blue-100 p-2">
            <div className="grid grid-cols-11 gap-1">
              <div></div>
              {COLS.map(col => (
                <div key={col} className="w-10 h-10 flex items-center justify-center font-bold text-blue-900">
                  {col}
                </div>
              ))}
              {ROWS.map((row, rowIdx) => (
                <React.Fragment key={row}>
                  <div className="w-10 h-10 flex items-center justify-center font-bold text-blue-900">
                    {row}
                  </div>
                  {COLS.map((col, colIdx) => {
                    const cellKey = `${rowIdx}-${colIdx}`;
                    const shipIdx = board[rowIdx][colIdx];
                    const isHovering = hovering && hovering.includes(cellKey);
                    const canPlace = currentShip < SHIPS.length && canPlaceShip(rowIdx, colIdx);

                    return (
                      <div
                        key={cellKey}
                        className={`w-10 h-10 border-2 border-blue-300 cursor-pointer transition-all ${
                          shipIdx !== null
                            ? SHIPS[shipIdx].color
                            : isHovering
                            ? canPlace
                              ? 'bg-green-300'
                              : 'bg-red-300'
                            : 'bg-blue-50 hover:bg-blue-200'
                        }`}
                        onClick={() => placeShip(rowIdx, colIdx)}
                        onMouseEnter={() => setHovering(getHoverCells(rowIdx, colIdx))}
                        onMouseLeave={() => setHovering(null)}
                      />
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>

        {/* Ships Placed */}
        <div className="mb-6">
          <h3 className="text-lg font-bold mb-2 text-gray-800">Ships Placed:</h3>
          <div className="space-y-2">
            {SHIPS.map((s, idx) => (
              <div key={s.name} className="flex items-center">
                <div className={`w-4 h-4 rounded ${s.color} mr-2`}></div>
                <span className={idx < placed.length ? 'text-gray-800' : 'text-gray-400'}>
                  {s.name} ({s.length})
                  {idx < placed.length && ` - ${placed[idx].cells.join(', ')}`}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Controls */}
        <div className="flex gap-4">
          <button
            onClick={reset}
            className="flex-1 px-6 py-3 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition font-bold"
          >
            Reset
          </button>
          {currentShip >= SHIPS.length && (
            <button
              onClick={() => setShowOutput(!showOutput)}
              className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-bold"
            >
              {showOutput ? 'Hide' : 'Show'} Ship Data
            </button>
          )}
        </div>

        {/* Output */}
        {showOutput && (
          <div className="mt-6 bg-gray-50 p-4 rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-bold text-gray-800">Your Ship Placements:</h3>
              <button
                onClick={copyToClipboard}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition text-sm"
              >
                Copy to Clipboard
              </button>
            </div>
            <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-sm">
              {exportJSON()}
            </pre>
            <p className="mt-2 text-sm text-gray-600">
              Copy this JSON and paste it into Claude chat to start the game!
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
