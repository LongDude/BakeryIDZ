const table_placeholder = document.getElementById('table_placeholder')

function request_table(table_name, page=1){
    while (table_placeholder.hasChildNodes()){
        table_placeholder.removeChild(table_placeholder.firstChild)
    }

    const params = new URLSearchParams({
        'page': page
    })


    fetch(`${table_name}?${params}`)
    .then(response => response.text())
    .catch(error => {
        console.error('Failed to fetch page: ', error)
    })
    .then(html => {
        const parser = new DOMParser()
        const doc = parser.parseFromString(html, 'text/html')
        
        return doc
    })
    .catch(error => {
        console.error('Failed parsing page: ', error)
    })
    .then(doc => {
        const panel = doc.getElementById('table-control')        
        const table = doc.getElementById('data-table')
        table_placeholder.appendChild(table)

        const page_buttons = panel.getElementsByClassName("paginate-button") 
        for (var i = 0; i < page_buttons.length; i++){
            const val = page_buttons[i].getAttribute('value')
            page_buttons[i].addEventListener('click', () => request_table(table_name, val))
        }
        table_placeholder.appendChild(panel)

    })
    .catch(error => {
        console.error('Failed appending page: ', error)
    })
}

document.getElementById('table-orders').addEventListener('click', () => request_table("orders"))
document.getElementById('table-sellings').addEventListener('click', () => request_table("sellings"))
document.getElementById('table-assortiment').addEventListener('click', () => request_table("assortiment"))
