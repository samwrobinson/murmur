module.exports = {
    name: "Murmur",
    description: "A pocket-sized voice journal. Press button, speak memory, done. No phone, no cloud, no distractions.",
    email: "",
    phoneForTel: "",
    phoneFormatted: "",
    address: {
        lineOne: "",
        lineTwo: "",
        city: "",
        state: "",
        zip: "",
        mapLink: "",
    },
    socials: [],
    //! Make sure you include the file protocol (e.g. https://) and that NO TRAILING SLASH is included
    domain: "https://murmur.local",
    // Passing the isProduction variable for use in HTML templates
    isProduction: process.env.ELEVENTY_ENV === "PROD",
    // API URL — points to Flask server
    apiUrl: process.env.ELEVENTY_ENV === "PROD"
        ? ""  // Same host in production (nginx proxies /api to Flask)
        : "http://localhost:5001",  // Dev: Flask runs on separate port
};
