const table_placeholder = document.getElementById('table_placeholder')
const addRowModalWindow = document.getElementById('add-row-modal') 
const rowModalBack = document.getElementById('row-modal-back')

var currentTable = "";
var currentPage = 1
const sortingOrderEnum = [null, 'asc', 'desc']
var sortingOrderMarkers = {};

const sortSVGtemplates = [
    document.getElementById('icons').content.childNodes[1],
    document.getElementById('icons').content.childNodes[5],
    document.getElementById('icons').content.childNodes[3]
]
const iconDecline = document.getElementById('icons').content.childNodes[7]
const iconApprove = document.getElementById('icons').content.childNodes[9]
const iconEdit = document.getElementById('icons').content.childNodes[11]
const iconDelete = document.getElementById('icons').content.childNodes[13]


rowModalBack.addEventListener('click', removePOSTForm)
addRowModalWindow.addEventListener('click', (event) => event.stopPropagation())


addRowModalWindow.addEventListener('submit', async (e) => {
    e.preventDefault()

    var response = null;
    var fields = {};

    switch(currentTable){
        case 'sellings': {
            fields = {
                // csrf_token:             document.getElementById('csrf_token'),
                product_id:             document.getElementById('product_id'),
                affiliate_id:           document.getElementById('affiliate_id'),
                goods_realised:         document.getElementById('goods_realised'),
                goods_realised_price:   document.getElementById('goods_realised_price'),
                goods_recieved:         document.getElementById('goods_recieved'),
                goods_recieved_cost:    document.getElementById('goods_recieved_cost'),
                date:                   document.getElementById('date')
            }
            
            response = await fetch(`/${currentTable}/add-form`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: fetchDocumentInput()
            })
            break
        }
        case 'orders': {
            break
        }
        case 'assortiment': {
            break
        }
        case _: {
            console.log('No table selected')
            break
        }
    }

    if (response.ok){
        console.log( await response.text)
        removePOSTForm()
        alert('Успех!')
    }
    else {
        alert('Ошибка ввода')
        const errors = await response.json;
        Object(errors).forEach((key) => {
            fields[key].classList.add('is-invalid');
        });
        console.log(errors)
    }
})


function fetchDocumentInput(suffix=''){
    // Суффикс позволяет использовать метод для product_id, edit_product_id и т.д.
    // Суффикс используется в основном из-за фильтров 
    switch (currentTable){
        case 'sellings': {
            return JSON.stringify({
                // csrf_token:             document.getElementById('csrf_token').value,
                product_id:             document.getElementById(`${suffix}product_id`).value,
                affiliate_id:           document.getElementById(`${suffix}affiliate_id`).value,
                goods_realised:         document.getElementById(`${suffix}goods_realised`).value,
                goods_realised_price:   document.getElementById(`${suffix}goods_realised_price`).value,
                goods_recieved:         document.getElementById(`${suffix}goods_recieved`).value,
                goods_recieved_cost:    document.getElementById(`${suffix}goods_recieved_cost`).value,
                date:                   document.getElementById(`${suffix}date`).value,
            })
        }
    }
}


function fetchRowID(row){
    //  Получаем ключи PK записи для указанной строки с учётом контекста таблицы

    switch (currentTable) {
        case 'sellings': {
            return new URLSearchParams({
                product_id: row.getAttribute('product_id'),
                affiliate_id: row.getAttribute('affiliate_id'),
                date: row.getAttribute('date')
            })
        }
    }
}

function changeSortingMode(colName){
    console.log(colName)

    let order = sortingOrderMarkers[colName][0]
    order = (order + 1) % 3
    sortingOrderMarkers[colName][0] = order
    const parent = sortingOrderMarkers[colName][1]
    parent.removeChild(parent.getElementsByTagName('svg')[0])
    let new_icon = sortSVGtemplates[order].cloneNode(true)
    new_icon.addEventListener('click', () => changeSortingMode(colName))
    parent.appendChild(new_icon)
    request_table(currentTable)
}

function request_table(table_name=currentTable, page=currentPage){
    while (table_placeholder.hasChildNodes()){
        table_placeholder.removeChild(table_placeholder.firstChild)
    }
    // Очищение промежуточных состояний таблицы
    currentltDeletingRow = null
    currentlyEditingRow = null
    removePOSTForm()

    // Если выбираем другую таблицу
    if (currentTable != table_name){
        currentPage = 1
        page = 1
    }
    else{
        currentPage = page
    }

    // ORDERING
    let sortOrders = []

    for (var key in sortingOrderMarkers){
        let order = sortingOrderMarkers[key][0] 
        if ( order > 0) {
            sortOrders.push(key)
            sortOrders.push(sortingOrderEnum[order])
        }
    }

    const params = new URLSearchParams({
        'page': page,
        'orderBy': sortOrders.join(',')
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
        const table = doc.getElementById('data-table-container')
        table_placeholder.appendChild(table)

        const page_buttons = panel.getElementsByClassName("paginate-button") 
        
        for (var i = 0; i < page_buttons.length; i++){
            const val = page_buttons[i].getAttribute('value')
            page_buttons[i].addEventListener('click', () => request_table(table_name, val))
        }

        // Настраиваем сортировку
        const colHeaders = document.querySelectorAll('#data-table thead th')
        console.log(colHeaders)
        // Выбрали другую таблицу
        if (currentTable != table_name){
            sortingOrderMarkers = {}   
            for (let i = 0; i < colHeaders.length - 1; i++){
                const text = colHeaders[i].firstChild.data
                
                // Сохраняем иконку в словарь
                sortingOrderMarkers[text] = [0, colHeaders[i]]
                colHeaders[i].getElementsByTagName('svg')[0].addEventListener('click', () => changeSortingMode(text))
            }
        }
        else{
            for (let i = 0; i < colHeaders.length - 1; i++){
                const text = colHeaders[i].firstChild.data
                const order = sortingOrderMarkers[text][0]
                const parent = colHeaders[i]
                // Записываем с учётом предыдущего состояния
                sortingOrderMarkers[text] = [order, parent]
                parent.removeChild(parent.getElementsByTagName('svg')[0])

                let newicon = sortSVGtemplates[order].cloneNode(true)
                newicon.addEventListener('click', () => changeSortingMode(text))
                parent.appendChild(newicon)
                
            }
        }

        const editGroups = document.getElementsByClassName('editButtons')
        console.log(editGroups)
        for (let i = 0; i < editGroups.length; i++){
            let btn = editGroups[i].firstElementChild
            const row = editGroups[i].parentElement
            btn.addEventListener('click', () => startLineEditing(row, editGroups[i] ))
            btn = btn.nextElementSibling
            btn.addEventListener('click', () => startLineDeleting(row, editGroups[i] ))
        } 

        const add_row_button = doc.getElementById("add-row")
        add_row_button.addEventListener('click', request_form_modal)

        table_placeholder.appendChild(panel)

        currentTable = table_name
    })
    .catch(error => {
        console.error('Failed appending page: ', error)
    })
}

var currentlyEditingRow = null // (row, controlCol)
var currentltDeletingRow = null // (row, controlCol)
function stopLineEditing(){
    if ( currentlyEditingRow === null){
        return
    }

    currentlyEditingRow[1].removeChild(currentlyEditingRow[1].firstElementChild)
    currentlyEditingRow[1].removeChild(currentlyEditingRow[1].firstElementChild)

    const editButton = iconEdit.cloneNode(true)
    const remButton = iconDelete.cloneNode(true)

    const row = currentlyEditingRow[0]
    const controlGroup = currentlyEditingRow[1]
    currentlyEditingRow = null

    editButton.addEventListener('click', () => startLineEditing(row, controlGroup))
    remButton.addEventListener('click', () => startLineDeleting(row, controlGroup))

    controlGroup.appendChild(editButton)
    controlGroup.appendChild(remButton)

    // removing edit lines
    const editColumns = row.getElementsByTagName('td')
    for (let i = 0; i < editColumns.length - 1; i++){
        editColumns[i].removeChild(editColumns[i].firstElementChild)
        editColumns[i].innerText = editColumns[i].getAttribute('old_text')
        editColumns[i].removeAttribute('old_text')
    }
}

function stopLineDeleting(){
    if ( currentltDeletingRow === null){
        return
    }

    currentltDeletingRow[1].removeChild(currentltDeletingRow[1].firstElementChild)
    currentltDeletingRow[1].removeChild(currentltDeletingRow[1].firstElementChild)

    const editButton = iconEdit.cloneNode(true)
    const remButton = iconDelete.cloneNode(true)

    const row = currentltDeletingRow[0]
    const controlGroup = currentltDeletingRow[1]
    currentltDeletingRow = null

    editButton.addEventListener('click', () => startLineEditing(row, controlGroup))
    remButton.addEventListener('click', () => startLineDeleting(row, controlGroup))

    controlGroup.appendChild(editButton)
    controlGroup.appendChild(remButton)
}

async function startLineEditing(callerRow, buttonCol){
    function _set_pk_line(column, input_f, pk_id){
        column.setAttribute('old_text', column.innerText)
        column.innerText = null
        column.appendChild(input_f)
        input_f.value = callerRow.getAttribute(pk_id)
    }


    stopLineDeleting()
    stopLineEditing()

    currentlyEditingRow = [callerRow, buttonCol]
    const apr = iconApprove.cloneNode(true)
    const cancel = iconDecline.cloneNode(true)

    buttonCol.removeChild(buttonCol.firstElementChild)
    buttonCol.removeChild(buttonCol.firstElementChild)

    apr.addEventListener('click', editRow)
    cancel.addEventListener('click', stopLineEditing)
    
    buttonCol.appendChild(apr)
    buttonCol.appendChild(cancel)

    // Add line editing
    switch (currentTable) {
        case 'sellings': {
            await fetch(`${currentTable}/functions`)
            .then(response => response.text())
            .catch(error => {
                console.log("Failed to fetch functions: ", error)
            })
            .then(html => {
                const parser = new DOMParser()
                const doc = parser.parseFromString(html, 'text/html')
                return doc
            })
            .catch(error => {
                console.log("Failed to parse page", error)
            })
            .then(doc => {
                // Parsing input fields
                const inputFields = [
                    doc.getElementById('product_id'),
                    doc.getElementById('affiliate_id'),
                    doc.getElementById('goods_realised'),
                    doc.getElementById('goods_realised_price'),
                    doc.getElementById('goods_recieved'),
                    doc.getElementById('goods_recieved_cost'),
                    doc.getElementById('date')
                ]
                
                // Changing names
                inputFields.forEach((el) => {
                    // console.log(el)
                    el.setAttribute('id', 'edit_' + el.getAttribute('id'))
                })

                const columns = callerRow.getElementsByTagName('td')
                
                _set_pk_line(columns[0], inputFields[0], 'product_id')
                _set_pk_line(columns[1], inputFields[1], 'affiliate_id')
                _set_pk_line(columns[6], inputFields[6], 'date')
                // 2.goods_realised
                // 3.goods_realised_price
                // 4.goods_recieves
                // 5.goods_recieved_cost
                for (let i = 2; i <= 5; i++){
                    inputFields[i].value = columns[i].innerText
                    columns[i].setAttribute('old_text', columns[i].innerText)
                    columns[i].innerText = null
                    columns[i].appendChild(inputFields[i])
                }
            })
            break
        }
    }
}

function startLineDeleting(callerRow, buttonCol){
    stopLineDeleting()
    stopLineEditing()

    currentltDeletingRow = [callerRow, buttonCol]
    const apr = iconApprove.cloneNode(true)
    const cancel = iconDecline.cloneNode(true)

    buttonCol.removeChild(buttonCol.firstElementChild)
    buttonCol.removeChild(buttonCol.firstElementChild)

    apr.addEventListener('click', deleteRow)
    cancel.addEventListener('click', stopLineDeleting)
    
    buttonCol.appendChild(apr)
    buttonCol.appendChild(cancel)
}

async function deleteRow(){
    const row = currentltDeletingRow[0]
    const params = new URLSearchParams(fetchRowID(row))

    let response = await fetch(`${currentTable}/del-form?${params}`, {method: 'DELETE'})
    
    if (response.ok){
        console.log(await response.text)
        alert('Удалено')
    }
    else{
        alert('Ошибка удаления')
        const errors = await response.json;
        Object(errors).forEach((key) => {
            fields[key].classList.add('is-invalid');
        });
        console.log(errors)
    }
    currentltDeletingRow = null
    request_table()
}

async function editRow(){
    const row = currentlyEditingRow[0]
    // Получаем PK_ID для записи и сохраняем как часть запроса
    const params = new URLSearchParams(fetchRowID(row))
    const response = await fetch(`${currentTable}/edit-form?${params}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: fetchDocumentInput('edit_')
    })

    if (response.ok){
        alert('Запись успешно обновлена!')
        request_table()
        console.log(await response.text)
    }
    else{
        alert('Непредвиденная ошибка')
        const error = await response.json;
        console.log(error)
    }
    
    stopLineEditing()
}

function request_form_modal(){
    if (currentTable.length == 0){
        console.log(currentTable, "is empty string")
    }

    fetch(`${currentTable}/add-form`)
    .then(response => response.text())
    .catch(error => {
        console.log("Failed to fetch modal window: ", error)
    })
    .then(html => {
        const parser = new DOMParser()
        const doc = parser.parseFromString(html, 'text/html')
        return doc
    })
    .catch(error => {
        console.log("Failed to parse page", error)
    })
    .then(doc => {
        rowModalBack.removeAttribute('hidden')
        addRowModalWindow.appendChild(doc.getElementById('form-add'))

    })
}

function removePOSTForm(){
    stopLineDeleting()
    stopLineEditing()

    if (!rowModalBack.hasAttribute('hidden')){
        rowModalBack.setAttribute('hidden', 'true')
        request_table()
    }
    while (addRowModalWindow.hasChildNodes()){
        addRowModalWindow.removeChild(addRowModalWindow.firstChild)
    }
}

document.getElementById('table-orders').addEventListener('click', () => request_table("orders"))
document.getElementById('table-sellings').addEventListener('click', () => request_table("sellings"))
document.getElementById('table-assortiment').addEventListener('click', () => request_table("assortiment"))