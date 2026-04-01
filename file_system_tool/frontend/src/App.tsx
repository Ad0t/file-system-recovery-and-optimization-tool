function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
        <h1 className="text-3xl font-bold text-primary mb-4">
          File System Recovery Tool
        </h1>
        <p className="text-gray-600 mb-6">
          React + TypeScript + Tailwind CSS + Vite setup complete!
        </p>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-success"></span>
            <span className="text-sm text-gray-700">Tailwind CSS configured</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-primary"></span>
            <span className="text-sm text-gray-700">TypeScript ready</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-secondary"></span>
            <span className="text-sm text-gray-700">Vite dev server</span>
          </div>
        </div>
        <button className="mt-6 w-full bg-primary text-white py-2 px-4 rounded hover:bg-blue-600 transition-colors">
          Get Started
        </button>
      </div>
    </div>
  )
}

export default App
