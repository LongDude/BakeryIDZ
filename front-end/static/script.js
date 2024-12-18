const table_placeholder = document.getElementById('table_placeholder')

function request_table(table_name){
    while (table_placeholder.hasChildNodes()){
        table_placeholder.removeChild(table_placeholder.firstChild)
    }

    fetch(`${table_name}`)
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
        console.log(doc); 
        const table = doc.getElementsByClassName('table')[0]
        console.log(table)
        table_placeholder.appendChild(table)
    })
    .catch(error => {
        console.error('Failed appending page: ', error)
    })
}

document.getElementById('table-orders').addEventListener('click', () => request_table("orders"))
document.getElementById('table-sellings').addEventListener('click', () => request_table("sellings"))
document.getElementById('table-assortiment').addEventListener('click', () => request_table("assortiment"))
