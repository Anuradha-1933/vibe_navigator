// src/App.js
import React, { useState } from 'react';
import axios from 'axios';
import './App.css';
import SearchBar from './components/SearchBar';
import PlaceList from './components/PlaceList';

function App() {
  // State for the main App: results from the API, loading status, and errors.
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // This function is passed down to the SearchBar component.
  // It's how the child (SearchBar) can send data back up to the parent (App).
  const handleSearch = async ({ query, city }) => {
    setLoading(true); // Start the loading spinner.
    setError(''); // Clear any previous errors.
    setResults([]); // Clear previous results.

    try {
      // Here is the main API call to our backend's search endpoint!
      const response = await axios.get('http://127.0.0.1:8000/search/', {
        params: {
          // `params` will turn into URL query parameters like:
          // ?query=cozy%20cafe&city=New%20York
          query: query,
          city: city,
        },
      });
      // Store the search results from the API into our component's memory.
      setResults(response.data.results);
    } catch (err) {
      setError('Sorry, something went wrong. Please try again.');
      console.error(err);
    } finally {
      // This `finally` block runs whether the API call succeeded or failed.
      setLoading(false); // Stop the loading spinner.
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Vibe Navigator 🧭</h1>
        <p>Find the perfect spot based on its vibe, not just its rating.</p>
      </header>

      <main>
        {/* We render the SearchBar component and pass it the handleSearch function */}
        <SearchBar onSearch={handleSearch} />

        {/* Conditional Rendering: Show a message while loading */}
        {loading && <p className="loading-message">Finding places...</p>}

        {/* Conditional Rendering: Show a message if there was an error */}
        {error && <p className="error-message">{error}</p>}

        {/* 
          Conditional Rendering: Only show the PlaceList if we are NOT loading
          and there are actually results to show.
        */}
        {!loading && results.length > 0 && <PlaceList places={results} />}
      </main>
    </div>
  );
}

export default App;