document.addEventListener('DOMContentLoaded', function() {
  var dropdown = document.querySelector('.user-dropdown');
  if (dropdown) {
    dropdown.addEventListener('click', function(event) {
      if (event.target.closest('a')) return;
      var dropdownContent = this.querySelector('.dropdown-content');
      dropdownContent.style.display = dropdownContent.style.display === 'block' ? 'none' : 'block';
    });
  }
});


window.onload = function() {
  // Assuming your flash messages have a class 'flash-message'
  var flashMessages = document.querySelectorAll('.flash-message');
  if(flashMessages.length) {
    history.replaceState(null, null, window.location.href.split('?')[0]);
  }
  // Then fade out or remove the flash messages as before
  setTimeout(function() {
    flashMessages.forEach(function(msg) {
      msg.style.opacity = '0';
      setTimeout(function() { msg.style.display = 'none'; }, 500);
    });
  }, 3000); // adjust timing as needed
};

function ClaimTicket(ticketId) {
    fetch(`/claim_ticket/${ticketId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'same-origin'
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Network response was not ok.');
        }
    })
    .then(data => {
        if (!data.message) throw new Error('The server did not confirm the ticket claim.');
        location.reload();
    })
    .catch(error => {
        console.error('Failed to claim ticket: ', error);
        window.alert(error.message);
    });
}