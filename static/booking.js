'use strict';
const form = document.getElementById('booking-form');
const checkIn = document.getElementById('check-in');
const checkOut = document.getElementById('check-out');
const adults = document.getElementById('adults');
const children = document.getElementById('children');
const total = document.getElementById('booking-total');
const duration = document.getElementById('booking-duration');
const hint = document.getElementById('booking-hint');
const money = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 0});
function updateBooking() {
  const start = checkIn.valueAsNumber;
  const end = checkOut.valueAsNumber;
  const nights = (end - start) / 86400000;
  checkOut.min = Number.isFinite(start) ? new Date(start + 86400000).toISOString().slice(0, 10) : checkIn.min;
  const tooMany = Number(adults.value) + Number(children.value) > Number(form.dataset.capacity);
  children.setCustomValidity(tooMany ? `This property accommodates up to ${form.dataset.capacity} guests.` : '');
  const validDates = Number.isInteger(nights) && nights > 0 && checkIn.value >= checkIn.min;
  total.textContent = validDates ? `${money.format(nights * Number(form.dataset.price))} total` : `${money.format(Number(form.dataset.price))} / night`;
  duration.textContent = validDates ? `${nights + 1} days · ${nights} night${nights === 1 ? '' : 's'}` : 'Select check-in and check-out';
  hint.textContent = tooMany ? `Please select no more than ${form.dataset.capacity} guests.` : validDates ? 'Price is per property, per night. No payment required.' : 'Choose a check-out date after check-in. Past dates cannot be booked.';
}
form.addEventListener('input', updateBooking);
form.addEventListener('submit', () => {
  document.getElementById('book-button').disabled = true;
  document.getElementById('book-button').textContent = 'Booking…';
});
window.addEventListener('pageshow', () => { document.getElementById('book-button').disabled = false; });
updateBooking();
