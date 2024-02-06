import logging
from odoo import http, _
from odoo.http import request, Response
import odoo
import json
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
from . import constants
from odoo.exceptions import AccessDenied, AccessError
log = logging.getLogger(__name__)



class TokenController(http.Controller):
    
    @http.route('/azk/get_token', methods=['GET', 'POST'], type='http', auth='none',cors='*',  csrf=False)
    def get_token(self, **kw):
        """
            Authenticate user and generate access token for him
        """
        try:
            response = None
            result = {
                        'status': constants.STATUS_OK,
                        'message': '',
                        'payload': '',
                        }

            user_name = kw.get('username')
            password = kw.get('password')
            db_name = odoo.tools.config.get('db_name')
            
            
            if not user_name or not password:
                result['status'] = constants.STATUS_FAIL
                result['message'] = constants.MSG_MISSING_USER_PASSWORD
                
                response =  Response(response=json.dumps(result), status=400)
            else:
                request.session.authenticate(db_name, user_name, password)
                
                uid = request.session.uid
                
                if not uid:
                    result['status'] = constants.STATUS_FAIL
                    result['message'] =  constants.MSG_LOGIN_FAILED
                    
                    response =  Response(response=json.dumps(result), status=401)
                    log.info("Authentication failed for user %s", user_name)
                else:
                    token_model = request.env['az.api.access.token'].sudo()  
                    token = token_model.create_token(request.env.user)
                    
                    result['status'] = constants.STATUS_SUCCESS
                    result['payload'] =   {
                                            'access_token': token.api_token,

                                            'token_exp_date': token.expiry_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if token.expiry_date else False,
                                        }
              
                    response =Response(response= json.dumps(result), status=200, )
  
                    log.info("New access token has been generated for user %s", user_name, exc_info=1)
                    
        except AccessDenied as e:
            result['status'] = constants.STATUS_FAIL
            result['message'] =  constants.MSG_ACCESS_DENIED
            response =  Response(json.dumps(result), status=403)
            log.info("Error occurred when trying to generate access token",  exc_info=1)
        except Exception as e:
            result['status'] = constants.STATUS_FAIL
            result['message'] =  constants.MSG_SERVER_ERROR
            response =  Response(json.dumps(result), status=500)
            log.info("Error occurred when trying to generate access token",  exc_info=1)
            
        return response
            
            
    @http.route('/azk/generate_lead', methods=['POST'], type='http', auth='none', cors='*', csrf=False)
    def generate_lead(self, **kw):
        """
            Authenticate user based on access token
            if authenticated, create  lead or return authentication error
        """
        try:
            response = None
            result = {
                        'status': constants.STATUS_OK,
                        'message': '',
                        'payload': '',
                        }
            token_model = request.env['az.api.access.token'].sudo()

            token = kw.get('access_token')
            
            token, err_msg = token_model.check_access_token(token)
            
            if not token:
                result['status'] = constants.STATUS_FAIL
                result['message'] =  err_msg
               
                response =  Response(json.dumps(result), status=401)
            else:
                token.update_token_last_accessed()
                request.session.uid = token.user_id.id
                
                user_context = request.env(request.cr, request.session.uid)['res.users'].context_get().copy()
                user_context['uid'] = request.session.uid
                request.session.context.update(user_context)
                request.context = user_context
                
                cr, uid = request.cr, request.session.uid
                cr._cnx.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)
                
                
                lead_model = request.env(cr, uid)['crm.lead']
                
                name = kw.get('name', '')
                email = kw.get('email', '')
                company = kw.get('company', '')
                profile_link = kw.get('profile', '')
                website = kw.get('website', '')
                phone = kw.get('phone', '')
                address = kw.get('address', '')
                city_country = kw.get('city_country', '')
                sales_nav_notes = kw.get('notes', '')
                position = kw.get('position')
                
                city, country, country_id = '', False, False
                
                if city_country:
                    city_country_list = city_country.split(',')
                    if len(city_country_list) > 1:
                        city = city_country_list[0].strip()
                        country = city_country_list[-1].strip().lower()
                    else:
                        country = city_country_list[0].strip().lower()
                        
                    if country:
                        country_id = request.env['res.country'].sudo().search([('name', 'ilike', country)], limit=1)
                        if country_id:
                            country_id =  country_id.id
                            
                notes = '<br/>'
                if sales_nav_notes:
                    sales_nav_notes = json.loads(sales_nav_notes)
                    for note in sales_nav_notes:
                        notes = notes + note + '<br/>'      
                
                source = request.env['utm.source'].sudo().search([('id', '=', 141)])
                medium = request.env['utm.medium'].sudo().search([('id', '=', 3)])
                
                lead = lead_model.create({
                                            'name': (company or name) + _("'s opportunity"),
                                            'contact_name': name,
                                            'email_from': email,
                                            'website': website,
                                            'partner_name': company,
                                            'description': profile_link + notes,
                                            'phone': phone,
                                            'city': city,
                                            'country_id': country_id,
                                            'street': address,
                                            'source_id': source.id if source else False,
                                            'medium_id': medium.id if medium else False,
                                            'function': position,
                                            'type': 'lead',
                                        })
                
                kw.pop('access_token')
                body = ''
                for key, val in kw.items():
                    body = body + '<b>' + key + '</b>: ' + val + '<br/>'
                lead.message_post(body=body)
  
                result['status'] = constants.STATUS_SUCCESS
                result['payload'] =   {'lead_id': lead.id, 'lead_name': lead.name}
                response = Response(json.dumps(result), status=200)
        
        except AccessError as e:
            result['status'] = constants.STATUS_FAIL
            result['message'] =  constants.MSG_ACCESS_RIGHTS_ERROR
            response =  Response(json.dumps(result), status=403)
            log.info("Error occurred when trying to generate lead",  exc_info=1)
        except Exception as e:
            result['status'] = constants.STATUS_FAIL
            result['message'] = constants.MSG_SERVER_ERROR
            response =  Response(json.dumps(result), status=500)
            log.info("Error occurred when trying to generate lead",  exc_info=1)
            
        return response
                

