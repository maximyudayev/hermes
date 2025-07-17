// assets/keyboard_events.js
// This script listens for keyboard events, updated from the previous version that used intervals

// Wait for Dash to be ready
var checkDashReady = setInterval(function() {
    if (window.dash_clientside && window.dash_clientside.set_props) {
        clearInterval(checkDashReady);
        
        // Set up keyboard listener
        document.addEventListener('keydown', function(e) {
            const key = e.key;
            const shiftKey = e.shiftKey;
            const ctrlKey = e.ctrlKey;
            
            // Check if we're in an input field
            const activeElement = document.activeElement;
            const isInputField = activeElement && (
                activeElement.tagName === 'INPUT' || 
                activeElement.tagName === 'TEXTAREA' ||
                activeElement.contentEditable === 'true'
            );
            
            // Skip if in input field unless it's a navigation key
            if (isInputField && !['ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown'].includes(key)) {
                return;
            }
            
            let eventData = null;
            
            // Navigation keys
            if (key === 'ArrowLeft' || key === 'ArrowRight' || 
                key === 'PageUp' || key === 'PageDown') {
                e.preventDefault();
                eventData = {
                    'key': key,
                    'shift': shiftKey,
                    'ctrl': ctrlKey,
                    'type': 'navigation',
                    'timestamp': Date.now()
                };
            }
            // N key for next input (only when not in input field)
            else if (!isInputField && (key === 'n' || key === 'N')) {
                e.preventDefault();
                eventData = {
                    'key': 'N',
                    'type': 'nextInput',
                    'timestamp': Date.now()
                };
            }
            // Number keys for label selection (only when not in input field)
            else if (!isInputField && key >= '0' && key <= '9') {
                e.preventDefault();
                eventData = {
                    'key': key,
                    'type': 'labelSelect',
                    'timestamp': Date.now()
                };
            }
            
            if (eventData) {
                // Directly update the Dash store
                window.dash_clientside.set_props("keyboard-event", {data: eventData});
            }
        });
        
        console.log("Keyboard listener initialized successfully");
    }
}, 100);